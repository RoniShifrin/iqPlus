"""Parent-specific API routes.

Data flow (same logic as Student, extended to N children):
  parent.linked_student_ids → CourseService.get_courses_for_students(ids)
                             → enrollments → courses
  Then enriched with child_name + teacher_name for display.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

from app.models import User, RoleEnum, EnrollmentStatusEnum
from app.security import get_current_user
from app.repositories import UserRepository
from app.services import CourseService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/parent", tags=["parent"])


@router.get("/courses")
async def get_parent_courses(current_user: User = Depends(get_current_user)):
    """
    Return every enrolled course for all of the parent's linked children.

    Reuses CourseService.get_courses_for_students — the same function that
    powers the Student flow — but passes all children's IDs at once.
    Results are enriched with child_name and teacher_name for display.
    """
    if current_user.role != RoleEnum.PARENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is for parents only",
        )

    linked_ids: List[str] = current_user.linked_student_ids or []
    logger.debug("[parent/courses] parent=%s  children_ids=%s", str(current_user.id), linked_ids)

    if not linked_ids:
        return []

    # ── 1. Resolve child names (presentation only) ─────────────────────────
    child_names: dict[str, str] = {}
    for sid in linked_ids:
        child = await UserRepository.get_by_id(sid)
        if child:
            child_names[sid] = child.full_name()
        else:
            logger.warning("[parent/courses] linked child %s not found in DB", sid)

    logger.debug("[parent/courses] children resolved: %s", list(child_names.keys()))

    # ── 2. Shared core: children → enrollments → courses ───────────────────
    #     Same logic as Student, just with multiple IDs.
    rows = await CourseService.get_courses_for_students(
        linked_ids,
        statuses=[EnrollmentStatusEnum.ACTIVE, EnrollmentStatusEnum.PENDING],
    )
    # rows == [{"course": Course, "student_id": str, "enrollment_status": EnrollmentStatusEnum}]

    # ── 3. Batch-fetch teacher names (presentation only) ───────────────────
    teacher_ids = list({row["course"].teacher_id for row in rows if row["course"].teacher_id})
    teacher_map: dict[str, str] = {}
    for tid in teacher_ids:
        teacher = await UserRepository.get_by_id(tid)
        if teacher:
            teacher_map[tid] = teacher.full_name()

    # ── 4. Build response — one row per (child × course) enrollment ────────
    result = []
    for row in rows:
        course = row["course"]
        enr_status = (
            row["enrollment_status"].value
            if hasattr(row["enrollment_status"], "value")
            else row["enrollment_status"]
        )
        result.append({
            "id":               str(course.id),
            "name":             course.name,
            "code":             course.code,
            "description":      course.description,
            "capacity":         course.capacity,
            "status":           course.status.value if hasattr(course.status, "value") else course.status,
            "visibility_scope": course.visibility_scope.value if hasattr(course.visibility_scope, "value") else course.visibility_scope,
            "schedule":         course.schedule,
            "teacher_id":       course.teacher_id,
            "teacher_name":     teacher_map.get(course.teacher_id),
            "child_id":         row["student_id"],
            "child_name":       child_names.get(row["student_id"], "Unknown"),
            "enrollment_status": enr_status,
        })

    logger.debug("[parent/courses] result rows: %d", len(result))
    return result
