"""Internal Chat API — threaded conversations (direct and course-scoped).

Permissions
-----------
Direct chat:
  ADMIN         → anyone
  TEACHER ↔ TEACHER  → always allowed
  TEACHER ↔ STUDENT  → must share an active course
  STUDENT ↔ STUDENT  → must share an active course
  Others        → blocked

Course chat:
  ADMIN          → allowed
  TEACHER        → must teach the course
  STUDENT        → must be actively enrolled in the course

Routes
------
POST /api/chat/conversations              — get or create conversation
GET  /api/chat/conversations              — list my conversations
GET  /api/chat/contacts                   — valid direct-chat recipients
GET  /api/chat/conversations/{id}/messages
POST /api/chat/conversations/{id}/messages
POST /api/chat/conversations/{id}/read
"""
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.models import (
    User, RoleEnum, EnrollmentStatusEnum,
    Conversation, ConversationTypeEnum, NotificationTypeEnum,
)
from app.schemas import (
    ConversationStartRequest, ChatMessageCreate,
    ChatMessageResponse, ConversationResponse, ChatContactResponse, PresenceItem,
)
from app.security import get_current_user
from app.repositories import (
    UserRepository, CourseRepository, EnrollmentRepository,
    ConversationRepository, ChatMessageRepository, NotificationRepository,
)

router = APIRouter(prefix="/api/chat", tags=["chat"])


# ── Permission helpers ────────────────────────────────────────────────────────

async def _shared_course_id(teacher_id: str, student_id: str) -> Optional[str]:
    """Return the first active shared course_id between a teacher and student."""
    teacher_courses = await CourseRepository.list_by_teacher(teacher_id)
    teacher_ids = {str(c.id) for c in teacher_courses}
    if not teacher_ids:
        return None
    enrollments = await EnrollmentRepository.list_by_student(student_id)
    for e in enrollments:
        if e.status == EnrollmentStatusEnum.ACTIVE and e.course_id in teacher_ids:
            return e.course_id
    return None


async def _students_share_course(s1_id: str, s2_id: str) -> bool:
    """Return True if two students share at least one active course."""
    e1 = await EnrollmentRepository.list_by_student(s1_id)
    ids1 = {e.course_id for e in e1 if e.status == EnrollmentStatusEnum.ACTIVE}
    if not ids1:
        return False
    e2 = await EnrollmentRepository.list_by_student(s2_id)
    return any(e.course_id in ids1 for e in e2 if e.status == EnrollmentStatusEnum.ACTIVE)


async def _can_direct_chat(user1: User, user2: User) -> bool:
    r1, r2 = user1.role, user2.role
    if r1 == RoleEnum.ADMIN or r2 == RoleEnum.ADMIN:
        return True
    if r1 == RoleEnum.TEACHER and r2 == RoleEnum.TEACHER:
        return True
    if r1 == RoleEnum.TEACHER and r2 == RoleEnum.STUDENT:
        return bool(await _shared_course_id(str(user1.id), str(user2.id)))
    if r1 == RoleEnum.STUDENT and r2 == RoleEnum.TEACHER:
        return bool(await _shared_course_id(str(user2.id), str(user1.id)))
    if r1 == RoleEnum.STUDENT and r2 == RoleEnum.STUDENT:
        return await _students_share_course(str(user1.id), str(user2.id))
    return False


async def _can_access_course_chat(user: User, course) -> bool:
    if user.role == RoleEnum.ADMIN:
        return True
    if user.role == RoleEnum.TEACHER and course.teacher_id == str(user.id):
        return True
    if user.role == RoleEnum.STUDENT:
        enrollment = await EnrollmentRepository.get_by_student_course(str(user.id), str(course.id))
        return enrollment is not None and enrollment.status == EnrollmentStatusEnum.ACTIVE
    return False


async def _get_user_course_ids(user: User) -> List[str]:
    """Return all active course IDs related to the user (as teacher or enrolled student)."""
    if user.role == RoleEnum.TEACHER:
        courses = await CourseRepository.list_by_teacher(str(user.id))
        return [str(c.id) for c in courses]
    if user.role == RoleEnum.STUDENT:
        enrollments = await EnrollmentRepository.list_by_student(str(user.id))
        return [e.course_id for e in enrollments if e.status == EnrollmentStatusEnum.ACTIVE]
    if user.role == RoleEnum.ADMIN:
        # Admin sees course chats for all courses (fetch all course conversations via separate query)
        return []  # handled specially in list endpoint
    return []


# ── Serialize helpers ─────────────────────────────────────────────────────────

async def _serialize_message(msg, sender_name: str, sender_avatar_url: Optional[str] = None) -> ChatMessageResponse:
    return ChatMessageResponse(
        id=str(msg.id),
        conversation_id=msg.conversation_id,
        sender_id=msg.sender_id,
        sender_name=sender_name,
        sender_avatar_url=sender_avatar_url,
        content=msg.content,
        read_by=msg.read_by,
        created_at=msg.created_at,
    )


async def _build_conversation_response(
    conv: Conversation,
    current_user_id: str,
) -> ConversationResponse:
    unread = await ChatMessageRepository.count_unread(str(conv.id), current_user_id)
    other_name: Optional[str] = None
    course_name: Optional[str] = None

    other_avatar_url: Optional[str] = None
    if conv.type == ConversationTypeEnum.DIRECT:
        other_id = next((p for p in conv.participant_ids if p != current_user_id), None)
        if other_id:
            other = await UserRepository.get_by_id(other_id)
            other_name = other.full_name() if other else "Unknown"
            other_avatar_url = other.avatar_url if other else None
    elif conv.type == ConversationTypeEnum.COURSE and conv.course_id:
        course = await CourseRepository.get_by_id(conv.course_id)
        course_name = course.name if course else "Unknown Course"

    return ConversationResponse(
        id=str(conv.id),
        type=conv.type.value,
        participant_ids=conv.participant_ids,
        course_id=conv.course_id,
        other_participant_name=other_name,
        other_participant_avatar_url=other_avatar_url,
        course_name=course_name,
        last_message_at=conv.last_message_at,
        last_message_preview=conv.last_message_preview,
        unread_count=unread,
        created_at=conv.created_at,
    )


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/conversations", response_model=ConversationResponse, status_code=status.HTTP_200_OK)
async def start_conversation(
    body: ConversationStartRequest,
    current_user: User = Depends(get_current_user),
):
    """Get existing or create a new direct or course conversation."""
    uid = str(current_user.id)

    if body.type == "direct":
        if not body.participant_id:
            raise HTTPException(status_code=400, detail="participant_id required for direct chat")
        if body.participant_id == uid:
            raise HTTPException(status_code=400, detail="Cannot start a conversation with yourself")

        other = await UserRepository.get_by_id(body.participant_id)
        if not other:
            raise HTTPException(status_code=404, detail="User not found")

        if not await _can_direct_chat(current_user, other):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not permitted to chat with this user",
            )

        # Deduplicate: return existing conversation if one exists
        existing = await ConversationRepository.find_direct(uid, body.participant_id)
        if existing:
            return await _build_conversation_response(existing, uid)

        conv = await ConversationRepository.create(
            type=ConversationTypeEnum.DIRECT,
            participant_ids=[uid, body.participant_id],
        )
        return await _build_conversation_response(conv, uid)

    else:  # course
        if not body.course_id:
            raise HTTPException(status_code=400, detail="course_id required for course chat")

        course = await CourseRepository.get_by_id(body.course_id)
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")

        if not await _can_access_course_chat(current_user, course):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a member of this course",
            )

        existing = await ConversationRepository.find_course_chat(body.course_id)
        if existing:
            return await _build_conversation_response(existing, uid)

        conv = await ConversationRepository.create(
            type=ConversationTypeEnum.COURSE,
            course_id=body.course_id,
        )
        return await _build_conversation_response(conv, uid)


@router.get("/conversations", response_model=List[ConversationResponse])
async def list_conversations(current_user: User = Depends(get_current_user)):
    """List all conversations for the current user."""
    uid = str(current_user.id)

    direct_convs = await ConversationRepository.list_direct_for_user(uid)

    course_ids = await _get_user_course_ids(current_user)
    if current_user.role == RoleEnum.ADMIN:
        # Admin sees all course conversations
        course_convs = await Conversation.find({"type": "course"}).sort(
            -Conversation.last_message_at
        ).to_list()
    else:
        course_convs = await ConversationRepository.list_course_for_ids(course_ids)

    all_convs = sorted(
        direct_convs + course_convs,
        key=lambda c: c.last_message_at,
        reverse=True,
    )

    result = []
    for conv in all_convs:
        result.append(await _build_conversation_response(conv, uid))
    return result


@router.get("/contacts", response_model=List[ChatContactResponse])
async def get_chat_contacts(
    course_id: Optional[str] = Query(None, description="Filter contacts to a specific course"),
    current_user: User = Depends(get_current_user),
):
    """Return valid direct-chat recipients for the current user.

    If course_id is provided, only users from that course are returned and
    the caller must have access to the course.
    """
    uid = str(current_user.id)
    contacts: List[dict] = []
    seen: set = set()

    # ── Course-scoped filter ──────────────────────────────────────────────────
    if course_id:
        # Verify the calling user can access this course
        scoped_course = await CourseRepository.get_by_id(course_id)
        if not scoped_course:
            raise HTTPException(status_code=404, detail="Course not found")
        if not await _can_access_course_chat(current_user, scoped_course):
            raise HTTPException(status_code=403, detail="Not a member of this course")

        # Build contacts scoped to only this course
        enrollments = await EnrollmentRepository.list_by_course(course_id)

        # Always include the teacher (unless they are the caller)
        if scoped_course.teacher_id != uid:
            teacher = await UserRepository.get_by_id(scoped_course.teacher_id)
            if teacher:
                contacts.append({
                    "id": str(teacher.id),
                    "name": teacher.full_name(),
                    "role": "teacher",
                    "course_id": course_id,
                    "course_name": scoped_course.name,
                    "last_active_at": teacher.last_active_at,
                })
                seen.add(scoped_course.teacher_id)

        for e in enrollments:
            if e.status != EnrollmentStatusEnum.ACTIVE or e.student_id == uid:
                continue
            key = e.student_id
            if key in seen:
                continue
            seen.add(key)
            student = await UserRepository.get_by_id(e.student_id)
            if student:
                contacts.append({
                    "id": str(student.id),
                    "name": student.full_name(),
                    "role": "student",
                    "course_id": course_id,
                    "course_name": scoped_course.name,
                    "last_active_at": student.last_active_at,
                })
        return [ChatContactResponse(**c) for c in contacts]

    # ── Unscoped (all valid contacts) ─────────────────────────────────────────
    if current_user.role == RoleEnum.ADMIN:
        # Admin can chat with any active user
        users = await User.find_all().to_list()
        for u in users:
            if str(u.id) == uid:
                continue
            key = str(u.id)
            if key not in seen:
                seen.add(key)
                contacts.append({
                    "id": str(u.id),
                    "name": u.full_name(),
                    "role": u.role.value,
                    "last_active_at": u.last_active_at,
                })

    elif current_user.role == RoleEnum.TEACHER:
        # Other teachers
        teachers = await User.find(User.role == RoleEnum.TEACHER).to_list()
        for t in teachers:
            if str(t.id) == uid:
                continue
            key = str(t.id)
            if key not in seen:
                seen.add(key)
                contacts.append({
                    "id": str(t.id),
                    "name": t.full_name(),
                    "role": "teacher",
                    "last_active_at": t.last_active_at,
                })
        # Students in the teacher's courses — batch-load to avoid N+1
        from beanie import PydanticObjectId
        courses = await CourseRepository.list_by_teacher(uid)
        # Collect all active enrollments across all courses at once
        course_id_strs = [str(c.id) for c in courses]
        course_map_local = {str(c.id): c for c in courses}
        if course_id_strs:
            all_enrs = await Enrollment.find(
                {"course_id": {"$in": course_id_strs}, "status": EnrollmentStatusEnum.ACTIVE}
            ).to_list()
            # Collect unique student IDs (not yet seen)
            student_ids_needed = []
            enr_meta = []  # (student_id, course_id) tuples to add
            for e in all_enrs:
                key = (e.student_id, e.course_id)
                if key not in seen:
                    seen.add(key)
                    student_ids_needed.append(e.student_id)
                    enr_meta.append((e.student_id, e.course_id))
            # Batch-load all students at once
            if student_ids_needed:
                valid_oids = []
                for sid in student_ids_needed:
                    try:
                        valid_oids.append(PydanticObjectId(sid))
                    except Exception:
                        pass
                if valid_oids:
                    students_batch = await User.find({"_id": {"$in": valid_oids}}).to_list()
                    student_map_local = {str(s.id): s for s in students_batch}
                    for sid, cid in enr_meta:
                        s = student_map_local.get(sid)
                        course_obj = course_map_local.get(cid)
                        if s and course_obj:
                            contacts.append({
                                "id": str(s.id),
                                "name": s.full_name(),
                                "role": "student",
                                "course_id": cid,
                                "course_name": course_obj.name,
                                "last_active_at": s.last_active_at,
                            })

    elif current_user.role == RoleEnum.STUDENT:
        # Batch-load to avoid N+1 queries
        from beanie import PydanticObjectId
        enrollments = await EnrollmentRepository.list_by_student(uid)
        active_enrs = [e for e in enrollments if e.status == EnrollmentStatusEnum.ACTIVE]
        if not active_enrs:
            return [ChatContactResponse(**c) for c in contacts]

        # Batch-load all enrolled courses at once
        enrolled_course_ids = [e.course_id for e in active_enrs]
        valid_oids_c = []
        for cid in enrolled_course_ids:
            try:
                valid_oids_c.append(PydanticObjectId(cid))
            except Exception:
                pass
        my_courses_batch = await Course.find({"_id": {"$in": valid_oids_c}}).to_list() if valid_oids_c else []
        my_course_map = {str(c.id): c for c in my_courses_batch}

        # Collect all teacher IDs and all course peer enrollments in bulk
        teacher_ids_needed = []
        for e in active_enrs:
            course_obj = my_course_map.get(e.course_id)
            if course_obj and course_obj.teacher_id:
                t_key = (course_obj.teacher_id, e.course_id)
                if t_key not in seen:
                    seen.add(t_key)
                    teacher_ids_needed.append((course_obj.teacher_id, e.course_id))

        # Batch-load peer enrollments for all enrolled courses at once
        all_peer_enrs = await Enrollment.find(
            {"course_id": {"$in": enrolled_course_ids}, "status": EnrollmentStatusEnum.ACTIVE}
        ).to_list()

        # Collect unique user IDs to load
        user_ids_needed: set = set()
        for tid, _ in teacher_ids_needed:
            user_ids_needed.add(tid)
        for ce in all_peer_enrs:
            if ce.student_id != uid:
                user_ids_needed.add(ce.student_id)

        # Single batch user load
        all_user_oids = []
        for user_id_str in user_ids_needed:
            try:
                all_user_oids.append(PydanticObjectId(user_id_str))
            except Exception:
                pass
        user_batch_map: dict = {}
        if all_user_oids:
            users_batch = await User.find({"_id": {"$in": all_user_oids}}).to_list()
            user_batch_map = {str(u.id): u for u in users_batch}

        # Build teacher contacts
        for tid, cid in teacher_ids_needed:
            teacher = user_batch_map.get(tid)
            course_obj = my_course_map.get(cid)
            if teacher and course_obj:
                contacts.append({
                    "id": str(teacher.id),
                    "name": teacher.full_name(),
                    "role": "teacher",
                    "course_id": cid,
                    "course_name": course_obj.name,
                    "last_active_at": teacher.last_active_at,
                })

        # Build peer contacts
        for ce in all_peer_enrs:
            if ce.student_id == uid:
                continue
            key = (ce.student_id, ce.course_id)
            if key in seen:
                continue
            seen.add(key)
            peer = user_batch_map.get(ce.student_id)
            course_obj = my_course_map.get(ce.course_id)
            if peer and course_obj:
                contacts.append({
                    "id": str(peer.id),
                    "name": peer.full_name(),
                    "role": "student",
                    "course_id": ce.course_id,
                    "course_name": course_obj.name,
                    "last_active_at": peer.last_active_at,
                })

    return [ChatContactResponse(**c) for c in contacts]


@router.get("/presence", response_model=List[PresenceItem])
async def get_presence(
    user_ids: str = Query(..., description="Comma-separated user IDs"),
    current_user: User = Depends(get_current_user),
):
    """Return online/offline presence for a list of user IDs.

    Online = last_active_at within the last 5 minutes.
    """
    id_list = [uid.strip() for uid in user_ids.split(",")[:200] if uid.strip()][:50]  # cap at 50
    cutoff = datetime.utcnow() - timedelta(minutes=5)
    # Batch-load all users at once instead of N individual queries
    from beanie import PydanticObjectId
    valid_oids = []
    for uid_str in id_list:
        try:
            valid_oids.append(PydanticObjectId(uid_str))
        except Exception:
            pass
    presence_map: dict = {}
    if valid_oids:
        users_batch = await User.find({"_id": {"$in": valid_oids}}).to_list()
        presence_map = {str(u.id): u for u in users_batch}
    result: List[PresenceItem] = []
    for uid_str in id_list:
        u = presence_map.get(uid_str)
        if u:
            is_online = bool(u.last_active_at and u.last_active_at >= cutoff)
            result.append(PresenceItem(
                user_id=uid_str,
                is_online=is_online,
                last_active_at=u.last_active_at,
            ))
    return result


@router.get("/conversations/{conv_id}/messages", response_model=List[ChatMessageResponse])
async def get_messages(
    conv_id: str,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
):
    uid = str(current_user.id)
    conv = await ConversationRepository.get_by_id(conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Authorization
    await _assert_conv_access(conv, current_user)

    messages = await ChatMessageRepository.list_by_conversation(conv_id, limit=limit)

    result = []
    sender_cache: dict = {}  # sender_id → (full_name, avatar_url)
    for msg in messages:
        if msg.sender_id not in sender_cache:
            u = await UserRepository.get_by_id(msg.sender_id)
            sender_cache[msg.sender_id] = (u.full_name() if u else "Unknown", u.avatar_url if u else None)
        name, avatar_url = sender_cache[msg.sender_id]
        result.append(await _serialize_message(msg, name, avatar_url))
    return result


@router.post("/conversations/{conv_id}/messages", response_model=ChatMessageResponse, status_code=status.HTTP_201_CREATED)
async def send_message(
    conv_id: str,
    body: ChatMessageCreate,
    current_user: User = Depends(get_current_user),
):
    uid = str(current_user.id)
    conv = await ConversationRepository.get_by_id(conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    await _assert_conv_access(conv, current_user)

    msg = await ChatMessageRepository.create(
        conversation_id=conv_id,
        sender_id=uid,
        content=body.content,
    )
    await ConversationRepository.update_last_message(conv_id, body.content)

    # Notify other participants
    try:
        recipient_ids = _get_other_participant_ids(conv, uid)
        sender_name = current_user.full_name()
        for rid in recipient_ids:
            await NotificationRepository.create(
                user_id=rid,
                title=f"New message from {sender_name}",
                message=body.content[:80],
                type=NotificationTypeEnum.CHAT_MESSAGE,
                related_entity_type="conversation",
                related_entity_id=conv_id,
            )
    except Exception:
        pass  # never block the response

    return await _serialize_message(msg, current_user.full_name(), current_user.avatar_url)


@router.post("/conversations/{conv_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_read(
    conv_id: str,
    current_user: User = Depends(get_current_user),
):
    uid = str(current_user.id)
    conv = await ConversationRepository.get_by_id(conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    await _assert_conv_access(conv, current_user)
    await ChatMessageRepository.mark_conversation_read(conv_id, uid)


# ── Auth guard helper ─────────────────────────────────────────────────────────

async def _assert_conv_access(conv: Conversation, user: User) -> None:
    uid = str(user.id)
    if user.role == RoleEnum.ADMIN:
        return
    if conv.type == ConversationTypeEnum.DIRECT:
        if uid not in conv.participant_ids:
            raise HTTPException(status_code=403, detail="Not a participant in this conversation")
    else:  # COURSE
        if not conv.course_id:
            raise HTTPException(status_code=403, detail="Invalid course conversation")
        course = await CourseRepository.get_by_id(conv.course_id)
        if not course or not await _can_access_course_chat(user, course):
            raise HTTPException(status_code=403, detail="Not a member of this course")


def _get_other_participant_ids(conv: Conversation, sender_id: str) -> List[str]:
    """Return participant IDs to notify (everyone except the sender)."""
    if conv.type == ConversationTypeEnum.DIRECT:
        return [p for p in conv.participant_ids if p != sender_id]
    # For course chats we don't enumerate all members — notifications skipped for scalability
    return []
