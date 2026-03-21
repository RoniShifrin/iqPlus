"""Internal Messaging routes — course-scoped with permission enforcement.

Permissions:
  - ADMIN: unrestricted
  - TEACHER → STUDENT: must share an active course
  - STUDENT → TEACHER: must be enrolled in a course taught by that teacher
  - Other roles: blocked

POST /api/messages/            — send a message (course-scoped, with notification)
GET  /api/messages/contacts    — valid recipients for the current user
GET  /api/messages/inbox       — received messages
GET  /api/messages/sent        — sent messages
PUT  /api/messages/{id}/read   — mark as read
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from app.models import User, RoleEnum, Message, NotificationTypeEnum, EnrollmentStatusEnum
from app.schemas import MessageCreate, MessageResponse
from app.security import get_current_user
from app.repositories import (
    MessageRepository, UserRepository, CourseRepository,
    EnrollmentRepository, NotificationRepository,
)

router = APIRouter(prefix="/api/messages", tags=["messages"])


def _serialize(msg: Message) -> dict:
    return {
        "id": str(msg.id),
        "sender_id": msg.sender_id,
        "recipient_id": msg.recipient_id,
        "subject": msg.subject,
        "content": msg.content,
        "message_type": msg.message_type.value if hasattr(msg.message_type, "value") else msg.message_type,
        "course_id": getattr(msg, "course_id", None),
        "read_status": msg.read_status,
        "email_sent": msg.email_sent,
        "created_at": msg.created_at,
    }


async def _shared_course_id(teacher_id: str, student_id: str) -> Optional[str]:
    """Return the first active shared course_id between a teacher and student, or None."""
    teacher_courses = await CourseRepository.list_by_teacher(teacher_id)
    teacher_course_ids = {str(c.id) for c in teacher_courses}
    if not teacher_course_ids:
        return None
    enrollments = await EnrollmentRepository.list_by_student(student_id)
    for e in enrollments:
        if e.status == EnrollmentStatusEnum.ACTIVE and e.course_id in teacher_course_ids:
            return e.course_id
    return None


@router.post("/", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def send_message(
    body: MessageCreate,
    current_user: User = Depends(get_current_user),
):
    recipient = await UserRepository.get_by_id(body.recipient_id)
    if not recipient:
        raise HTTPException(status_code=404, detail="Recipient not found")

    # ── Course-based permission enforcement ────────────────────────────────
    if current_user.role != RoleEnum.ADMIN:
        sender_role = current_user.role
        recipient_role = recipient.role

        if sender_role == RoleEnum.TEACHER and recipient_role == RoleEnum.STUDENT:
            shared = await _shared_course_id(str(current_user.id), body.recipient_id)
            if not shared:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only message students enrolled in your courses",
                )
            if body.course_id:
                teacher_course_ids = {
                    str(c.id) for c in await CourseRepository.list_by_teacher(str(current_user.id))
                }
                if body.course_id not in teacher_course_ids:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Course does not belong to you",
                    )

        elif sender_role == RoleEnum.STUDENT and recipient_role == RoleEnum.TEACHER:
            shared = await _shared_course_id(body.recipient_id, str(current_user.id))
            if not shared:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only message teachers of courses you are enrolled in",
                )
            if body.course_id:
                enrollments = await EnrollmentRepository.list_by_student(str(current_user.id))
                active_course_ids = {
                    e.course_id for e in enrollments if e.status == EnrollmentStatusEnum.ACTIVE
                }
                if body.course_id not in active_course_ids:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="You are not enrolled in this course",
                    )

        elif sender_role == RoleEnum.PARENT and recipient_role == RoleEnum.TEACHER:
            # Parent may message teachers of their linked children's courses only
            linked_ids = current_user.linked_student_ids or []
            allowed = False
            for student_id in linked_ids:
                if await _shared_course_id(body.recipient_id, student_id):
                    allowed = True
                    break
            if not allowed:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only message teachers of your linked children's courses",
                )
            if body.course_id:
                course_ok = False
                for student_id in linked_ids:
                    enrs = await EnrollmentRepository.list_by_student(student_id)
                    for e in enrs:
                        if e.status == EnrollmentStatusEnum.ACTIVE and e.course_id == body.course_id:
                            course_ok = True
                            break
                    if course_ok:
                        break
                if not course_ok:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Course is not related to any of your linked children",
                    )

        elif sender_role == RoleEnum.TEACHER and recipient_role == RoleEnum.PARENT:
            # Teacher may message parents of students actively enrolled in their courses
            parent_linked_ids = recipient.linked_student_ids or []
            allowed = False
            for student_id in parent_linked_ids:
                if await _shared_course_id(str(current_user.id), student_id):
                    allowed = True
                    break
            if not allowed:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only message parents of students enrolled in your courses",
                )

        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Messaging is only available between teachers and their enrolled students",
            )

    # ── Optional external email delivery ───────────────────────────────────
    email_sent = False
    if body.send_email:
        try:
            from app.services.email_service import EmailNotificationService
            sender_name = current_user.full_name()
            html = (
                f"<p>You have a new message from <strong>{sender_name}</strong>:</p>"
                f"<h3>{body.subject}</h3>"
                f"<p>{body.content}</p>"
            )
            email_sent = EmailNotificationService.send_email(
                recipient=recipient.email,
                subject=f"IQ PLUS Message: {body.subject}",
                html_content=html,
            )
        except Exception:
            pass

    msg = await MessageRepository.create(
        sender_id=str(current_user.id),
        recipient_id=body.recipient_id,
        subject=body.subject,
        content=body.content,
        message_type=body.message_type,
        course_id=body.course_id,
        email_sent=email_sent,
    )

    # ── In-app notification for recipient ──────────────────────────────────
    try:
        await NotificationRepository.create(
            user_id=body.recipient_id,
            title=f"Message from {current_user.full_name()}",
            message=body.subject,
            type=NotificationTypeEnum.MESSAGE_RECEIVED,
            course_id=body.course_id,
            related_entity_type="message",
            related_entity_id=str(msg.id),
        )
    except Exception:
        pass  # Never block the response

    return MessageResponse(**_serialize(msg))


@router.get("/contacts")
async def get_contacts(current_user: User = Depends(get_current_user)):
    """Returns valid messaging contacts based on course relationships.

    Teacher  → all actively-enrolled students across their courses (one entry per course).
    Student  → all teachers of courses they are actively enrolled in.
    """
    contacts = []

    if current_user.role == RoleEnum.TEACHER:
        courses = await CourseRepository.list_by_teacher(str(current_user.id))
        seen: set = set()
        for course in courses:
            enrollments = await EnrollmentRepository.list_by_course(str(course.id))
            for e in enrollments:
                if e.status != EnrollmentStatusEnum.ACTIVE:
                    continue
                key = (e.student_id, str(course.id))
                if key in seen:
                    continue
                seen.add(key)
                student = await UserRepository.get_by_id(e.student_id)
                if student:
                    contacts.append({
                        "id": str(student.id),
                        "name": student.full_name(),
                        "role": "student",
                        "course_id": str(course.id),
                        "course_name": course.name,
                    })

    elif current_user.role == RoleEnum.STUDENT:
        enrollments = await EnrollmentRepository.list_by_student(str(current_user.id))
        seen_pairs: set = set()
        for e in enrollments:
            if e.status != EnrollmentStatusEnum.ACTIVE:
                continue
            course = await CourseRepository.get_by_id(e.course_id)
            if not course:
                continue
            key = (course.teacher_id, str(course.id))
            if key in seen_pairs:
                continue
            seen_pairs.add(key)
            teacher = await UserRepository.get_by_id(course.teacher_id)
            if teacher:
                contacts.append({
                    "id": str(teacher.id),
                    "name": teacher.full_name(),
                    "role": "teacher",
                    "course_id": str(course.id),
                    "course_name": course.name,
                })

    elif current_user.role == RoleEnum.PARENT:
        # One contact entry per (teacher, course) pair, tagged with which child
        linked_ids = current_user.linked_student_ids or []
        seen_pairs_p: set = set()
        for student_id in linked_ids:
            student = await UserRepository.get_by_id(student_id)
            if not student:
                continue
            enrollments = await EnrollmentRepository.list_by_student(student_id)
            for e in enrollments:
                if e.status != EnrollmentStatusEnum.ACTIVE:
                    continue
                course = await CourseRepository.get_by_id(e.course_id)
                if not course:
                    continue
                key = (course.teacher_id, str(course.id), student_id)
                if key in seen_pairs_p:
                    continue
                seen_pairs_p.add(key)
                teacher = await UserRepository.get_by_id(course.teacher_id)
                if teacher:
                    contacts.append({
                        "id": str(teacher.id),
                        "name": teacher.full_name(),
                        "role": "teacher",
                        "course_id": str(course.id),
                        "course_name": course.name,
                        "student_id": student_id,
                        "student_name": student.full_name(),
                    })

    return {"contacts": contacts}


@router.get("/inbox", response_model=List[MessageResponse])
async def inbox(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
):
    messages = await MessageRepository.inbox(str(current_user.id), limit=limit)
    return [MessageResponse(**_serialize(m)) for m in messages]


@router.get("/sent", response_model=List[MessageResponse])
async def sent_messages(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
):
    messages = await MessageRepository.sent(str(current_user.id), limit=limit)
    return [MessageResponse(**_serialize(m)) for m in messages]


@router.put("/{message_id}/read", response_model=MessageResponse)
async def mark_read(
    message_id: str,
    current_user: User = Depends(get_current_user),
):
    msg = await MessageRepository.get_by_id(message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    if msg.recipient_id != str(current_user.id) and current_user.role != RoleEnum.ADMIN:
        raise HTTPException(status_code=403, detail="Not your message")
    updated = await MessageRepository.mark_read(message_id)
    return MessageResponse(**_serialize(updated))
