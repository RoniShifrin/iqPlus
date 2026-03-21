"""Report export routes — PDF, CSV, and XLSX."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from app.models import User, RoleEnum
from app.security import get_current_user
from app.services.report_service import (
    generate_student_report, generate_course_report, generate_attendance_report,
)

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/student/{student_id}/export")
async def export_student_report(
    student_id: str,
    format: str = Query("pdf", pattern="^(pdf|csv|xlsx)$"),
    current_user: User = Depends(get_current_user),
):
    """Export a student progress report as PDF or CSV.

    Access: admin, the student themselves, a linked parent, or the course teacher.
    """
    if current_user.role == RoleEnum.STUDENT:
        if str(current_user.id) != student_id:
            raise HTTPException(status_code=403, detail="Cannot export another student's report")
    elif current_user.role == RoleEnum.PARENT:
        if student_id not in current_user.linked_student_ids:
            raise HTTPException(status_code=403, detail="Not linked to this student")
    elif current_user.role == RoleEnum.TEACHER:
        # Teacher may export reports for students enrolled in their courses
        from app.repositories import EnrollmentRepository, CourseRepository
        enrollments = await EnrollmentRepository.list_by_student(student_id)
        teacher_course_ids = {
            str(c.id)
            for c in await CourseRepository.list_by_teacher(str(current_user.id))
        }
        enrolled_ids = {e.course_id for e in enrollments}
        if not teacher_course_ids.intersection(enrolled_ids):
            raise HTTPException(status_code=403, detail="Student not enrolled in your courses")
    # ADMIN: no additional checks

    try:
        content, media_type, filename = await generate_student_report(student_id, fmt=format)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    disposition = f'attachment; filename="{filename}"'
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": disposition},
    )


@router.get("/course/{course_id}/export")
async def export_course_report(
    course_id: str,
    format: str = Query("csv", pattern="^(csv|xlsx)$"),
    current_user: User = Depends(get_current_user),
):
    """Export a course performance summary. Teachers (own course), admins."""
    if current_user.role == RoleEnum.TEACHER:
        from app.repositories import CourseRepository
        course = await CourseRepository.get_by_id(course_id)
        if not course or course.teacher_id != str(current_user.id):
            raise HTTPException(status_code=403, detail="Not your course")
    elif current_user.role != RoleEnum.ADMIN:
        raise HTTPException(status_code=403, detail="Not authorized")

    try:
        content, media_type, filename = await generate_course_report(course_id, fmt=format)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return Response(content=content, media_type=media_type,
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/attendance/{course_id}/export")
async def export_attendance_report(
    course_id: str,
    student_id: Optional[str] = Query(None),
    format: str = Query("csv", pattern="^(csv|xlsx)$"),
    current_user: User = Depends(get_current_user),
):
    """Export attendance for a course. Teachers (own course) + admins."""
    if current_user.role == RoleEnum.TEACHER:
        from app.repositories import CourseRepository
        course = await CourseRepository.get_by_id(course_id)
        if not course or course.teacher_id != str(current_user.id):
            raise HTTPException(status_code=403, detail="Not your course")
    elif current_user.role == RoleEnum.STUDENT:
        # Students may export their own attendance only
        student_id = str(current_user.id)
    elif current_user.role != RoleEnum.ADMIN:
        raise HTTPException(status_code=403, detail="Not authorized")

    try:
        content, media_type, filename = await generate_attendance_report(
            course_id, student_id=student_id, fmt=format
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return Response(content=content, media_type=media_type,
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})
