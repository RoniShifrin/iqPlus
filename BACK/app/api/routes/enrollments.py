"""Enrollment API routes"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional

from app.models import User, RoleEnum, EnrollmentStatusEnum, NotificationTypeEnum
from app.schemas import EnrollmentCreate, EnrollmentResponse, EnrollmentRequest, EnrollmentAction
from app.security import get_current_user
from app.repositories import (
    EnrollmentRepository, CourseRepository, UserRepository,
    NotificationRepository, AuditLogRepository
)
from app.services import EnrollmentService

router = APIRouter(prefix="/api/enrollments", tags=["enrollments"])


def _serialize_enrollment(e) -> dict:
    return {
        "id": str(e.id),
        "student_id": e.student_id,
        "course_id": e.course_id,
        "status": e.status,
        "enrolled_at": e.enrolled_at,
        "completed_at": e.completed_at,
    }


@router.post("/", response_model=EnrollmentResponse, status_code=status.HTTP_201_CREATED)
async def enroll_student(
    enrollment: EnrollmentCreate,
    current_user: User = Depends(get_current_user)
):
    """Admin or course-owner teacher: directly enroll a student (status=active)."""
    if current_user.role not in (RoleEnum.ADMIN, RoleEnum.TEACHER):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Teachers and admins only")

    course = await CourseRepository.get_by_id(enrollment.course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    # Teachers may only enroll into their own courses
    if current_user.role == RoleEnum.TEACHER and course.teacher_id != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only enroll students in your own courses")

    student = await UserRepository.get_by_id(enrollment.student_id)
    if not student or student.role != RoleEnum.STUDENT:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid student")

    # Prevent duplicate enrollment
    existing = await EnrollmentRepository.get_by_student_course(enrollment.student_id, enrollment.course_id)
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Student is already enrolled in this course")

    enrollment_result, error = await EnrollmentService.enroll_student(
        enrollment.student_id, enrollment.course_id
    )
    if error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)

    await NotificationRepository.create(
        user_id=enrollment.student_id,
        message=f"You have been enrolled in '{course.name}' by {current_user.full_name()}.",
        type=NotificationTypeEnum.ENROLLMENT_APPROVED
    )

    await AuditLogRepository.log(
        user_id=str(current_user.id),
        action="enroll_direct",
        resource_type="enrollment",
        resource_id=str(enrollment_result.id),
        details={"student_id": enrollment.student_id, "course_id": enrollment.course_id}
    )

    return EnrollmentResponse(**_serialize_enrollment(enrollment_result))


@router.post("/request", response_model=EnrollmentResponse, status_code=status.HTTP_201_CREATED)
async def request_enrollment(
    body: EnrollmentRequest,
    current_user: User = Depends(get_current_user)
):
    """Student (or parent on behalf of linked child) requests enrollment; status=pending for teacher/admin to approve."""
    if current_user.role == RoleEnum.PARENT:
        if not body.student_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="student_id required for parent enrollment requests")
        if body.student_id not in (current_user.linked_student_ids or []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your linked child")
        target_student_id = body.student_id
        requester_name = f"{current_user.full_name()} (parent)"
    elif current_user.role == RoleEnum.STUDENT:
        target_student_id = str(current_user.id)
        requester_name = current_user.full_name()
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Students and parents only")

    course = await CourseRepository.get_by_id(body.course_id)
    if not course or course.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    existing = await EnrollmentRepository.get_by_student_course(target_student_id, body.course_id)
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already enrolled or request pending")

    active_count = await EnrollmentRepository.count_active(body.course_id)
    if active_count >= course.capacity:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Course is at capacity")

    # Check for schedule conflicts with student's existing active enrollments
    conflict = await EnrollmentService.check_schedule_conflict(target_student_id, course)
    if conflict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "schedule_conflict",
                "course_id": conflict["course_id"],
                "course_name": conflict["course_name"],
                "day": conflict["day"],
                "start_time": conflict["start_time"],
                "end_time": conflict["end_time"],
            }
        )

    enrollment = await EnrollmentRepository.create(
        student_id=target_student_id,
        course_id=body.course_id,
        status=EnrollmentStatusEnum.PENDING
    )

    await NotificationRepository.create(
        user_id=course.teacher_id,
        message=f"New enrollment request for '{course.name}' from {requester_name}.",
        type=NotificationTypeEnum.ENROLLMENT_PENDING
    )

    await AuditLogRepository.log(
        user_id=str(current_user.id),
        action="enrollment_request",
        resource_type="enrollment",
        resource_id=str(enrollment.id),
        details={"course_id": body.course_id, "student_id": target_student_id}
    )

    return EnrollmentResponse(**_serialize_enrollment(enrollment))


@router.post("/{enrollment_id}/approve", response_model=EnrollmentResponse)
async def approve_enrollment(
    enrollment_id: str,
    body: EnrollmentAction = EnrollmentAction(),
    current_user: User = Depends(get_current_user)
):
    """Teacher or admin approves a pending enrollment."""
    enrollment = await EnrollmentRepository.get_by_id(enrollment_id)
    if not enrollment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment not found")
    if enrollment.status != EnrollmentStatusEnum.PENDING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Enrollment is not pending")

    course = await CourseRepository.get_by_id(enrollment.course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    is_teacher_owner = current_user.role == RoleEnum.TEACHER and course.teacher_id == str(current_user.id)
    if current_user.role != RoleEnum.ADMIN and not is_teacher_owner:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    active_count = await EnrollmentRepository.count_active(enrollment.course_id)
    if active_count >= course.capacity:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Course is now at capacity")

    await enrollment.set({"status": EnrollmentStatusEnum.ACTIVE})

    # Post-activation guard: re-count under the real committed state and revert if
    # two concurrent approvals both slipped past the pre-check above.
    confirmed_count = await EnrollmentRepository.count_active(enrollment.course_id)
    if confirmed_count > course.capacity:
        await enrollment.set({"status": EnrollmentStatusEnum.PENDING})
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Course just reached capacity. Enrollment reverted to pending."
        )

    await NotificationRepository.create(
        user_id=enrollment.student_id,
        title=course.name,
        message=f"Your enrollment request for '{course.name}' has been approved!",
        type=NotificationTypeEnum.ENROLLMENT_APPROVED,
        course_id=str(course.id),
        related_entity_type="enrollment",
        related_entity_id=enrollment_id,
    )

    # Notify any linked parents
    from app.models import User as UserModel
    linked_parents = await UserModel.find(
        {"role": "parent", "linked_student_ids": enrollment.student_id}
    ).to_list()
    for parent in linked_parents:
        await NotificationRepository.create(
            user_id=str(parent.id),
            title=course.name,
            message=f"Your child's enrollment request for '{course.name}' has been approved.",
            type=NotificationTypeEnum.ENROLLMENT_APPROVED,
            course_id=str(course.id),
            related_entity_type="enrollment",
            related_entity_id=enrollment_id,
        )

    await AuditLogRepository.log(
        user_id=str(current_user.id),
        action="enrollment_approved",
        resource_type="enrollment",
        resource_id=enrollment_id,
        details={"course_id": enrollment.course_id, "student_id": enrollment.student_id}
    )

    return EnrollmentResponse(**_serialize_enrollment(enrollment))


@router.post("/{enrollment_id}/reject", response_model=EnrollmentResponse)
async def reject_enrollment(
    enrollment_id: str,
    body: EnrollmentAction = EnrollmentAction(),
    current_user: User = Depends(get_current_user)
):
    """Teacher or admin rejects a pending enrollment."""
    enrollment = await EnrollmentRepository.get_by_id(enrollment_id)
    if not enrollment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment not found")
    if enrollment.status != EnrollmentStatusEnum.PENDING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Enrollment is not pending")

    course = await CourseRepository.get_by_id(enrollment.course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    is_teacher_owner = current_user.role == RoleEnum.TEACHER and course.teacher_id == str(current_user.id)
    if current_user.role != RoleEnum.ADMIN and not is_teacher_owner:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    await enrollment.set({"status": EnrollmentStatusEnum.REJECTED})

    reason_text = f" Reason: {body.reason}" if body.reason else ""
    await NotificationRepository.create(
        user_id=enrollment.student_id,
        title=course.name,
        message=f"Your enrollment request for '{course.name}' was rejected.{reason_text}",
        type=NotificationTypeEnum.ENROLLMENT_REJECTED,
        course_id=str(course.id),
        related_entity_type="enrollment",
        related_entity_id=enrollment_id,
    )

    # Notify any linked parents
    from app.models import User as UserModel
    linked_parents = await UserModel.find(
        {"role": "parent", "linked_student_ids": enrollment.student_id}
    ).to_list()
    for parent in linked_parents:
        await NotificationRepository.create(
            user_id=str(parent.id),
            title=course.name,
            message=f"Your child's enrollment request for '{course.name}' was rejected.{reason_text}",
            type=NotificationTypeEnum.ENROLLMENT_REJECTED,
            course_id=str(course.id),
            related_entity_type="enrollment",
            related_entity_id=enrollment_id,
        )

    await AuditLogRepository.log(
        user_id=str(current_user.id),
        action="enrollment_rejected",
        resource_type="enrollment",
        resource_id=enrollment_id,
        details={"course_id": enrollment.course_id, "student_id": enrollment.student_id}
    )

    return EnrollmentResponse(**_serialize_enrollment(enrollment))


@router.get("/", response_model=List[EnrollmentResponse])
async def list_enrollments(
    current_user: User = Depends(get_current_user),
    student_id: Optional[str] = None,
    course_id: Optional[str] = None,
    limit: int = 500,  # safety cap — prevents unbounded bulk export
):
    if current_user.role == RoleEnum.ADMIN:
        # Admins may query any student or course
        if student_id:
            enrollments = await EnrollmentRepository.list_by_student(student_id)
        elif course_id:
            enrollments = await EnrollmentRepository.list_by_course(course_id)
        else:
            enrollments = []
    elif current_user.role == RoleEnum.TEACHER:
        # Teachers may list enrollments for their own courses only
        if course_id:
            course = await CourseRepository.get_by_id(course_id)
            if not course or course.teacher_id != str(current_user.id):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your course")
            enrollments = await EnrollmentRepository.list_by_course(course_id)
        elif student_id:
            # Allow teacher to look up a specific student across their own courses
            all_enr = await EnrollmentRepository.list_by_student(student_id)
            teacher_course_ids = {
                str(c.id) for c in await CourseRepository.list_by_teacher(str(current_user.id))
            }
            enrollments = [e for e in all_enr if e.course_id in teacher_course_ids]
        else:
            # No filter: return all enrollments across all courses this teacher owns.
            # Required by the Lesson Records student selector which calls this with no params.
            teacher_courses = await CourseRepository.list_by_teacher(str(current_user.id))
            all_enrs: list = []
            for c in teacher_courses:
                course_enrs = await EnrollmentRepository.list_by_course(str(c.id))
                all_enrs.extend(course_enrs)
            enrollments = all_enrs[:limit]  # respect the safety cap
    elif current_user.role == RoleEnum.STUDENT:
        # Students may only see their own enrollments
        target = student_id or str(current_user.id)
        if target != str(current_user.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        enrollments = await EnrollmentRepository.list_by_student(str(current_user.id))
    elif current_user.role == RoleEnum.PARENT:
        # Parents may see enrollments for their linked children only
        if student_id:
            if student_id not in (current_user.linked_student_ids or []):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not linked to this student")
            enrollments = await EnrollmentRepository.list_by_student(student_id)
        else:
            enrollments = []
    else:
        enrollments = []
    return [EnrollmentResponse(**_serialize_enrollment(e)) for e in enrollments]


@router.get("/pending-teacher")
async def list_pending_teacher(
    current_user: User = Depends(get_current_user)
):
    """Teacher: enriched list of all PENDING enrollment requests for their courses."""
    if current_user.role not in (RoleEnum.ADMIN, RoleEnum.TEACHER):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Teachers and admins only")

    teacher_courses = await CourseRepository.list_by_teacher(str(current_user.id))
    result = []
    for course in teacher_courses:
        enrollments = await EnrollmentRepository.list_by_course(str(course.id))
        for e in enrollments:
            if e.status != EnrollmentStatusEnum.PENDING:
                continue
            student = await UserRepository.get_by_id(e.student_id)
            result.append({
                "enrollment_id": str(e.id),
                "student_id": e.student_id,
                "student_name": student.full_name() if student else e.student_id,
                "student_email": student.email if student else None,
                "course_id": str(course.id),
                "course_name": course.name,
                "requested_at": e.enrolled_at.isoformat() if e.enrolled_at else None,
            })
    return result


@router.get("/{enrollment_id}", response_model=EnrollmentResponse)
async def get_enrollment(
    enrollment_id: str,
    current_user: User = Depends(get_current_user)
):
    enrollment = await EnrollmentRepository.get_by_id(enrollment_id)
    if not enrollment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment not found")

    # Ownership check
    if current_user.role == RoleEnum.ADMIN:
        pass
    elif current_user.role == RoleEnum.STUDENT:
        if enrollment.student_id != str(current_user.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    elif current_user.role == RoleEnum.PARENT:
        if enrollment.student_id not in (current_user.linked_student_ids or []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not linked to this student")
    elif current_user.role == RoleEnum.TEACHER:
        course = await CourseRepository.get_by_id(enrollment.course_id)
        if not course or course.teacher_id != str(current_user.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your course")
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    return EnrollmentResponse(**_serialize_enrollment(enrollment))


@router.delete("/{enrollment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def withdraw_course(
    enrollment_id: str,
    current_user: User = Depends(get_current_user)
):
    enrollment = await EnrollmentRepository.get_by_id(enrollment_id)
    if not enrollment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment not found")

    if current_user.role == RoleEnum.ADMIN:
        pass  # admin can remove any enrollment
    elif enrollment.student_id == str(current_user.id):
        pass  # student withdrawing themselves
    elif current_user.role == RoleEnum.TEACHER:
        course = await CourseRepository.get_by_id(enrollment.course_id)
        if not course or course.teacher_id != str(current_user.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only remove students from your own courses")
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    await enrollment.set({"status": EnrollmentStatusEnum.WITHDRAWN})
