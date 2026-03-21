"""Lesson Records API routes.

Teachers create records; students/parents view their own.
Each POST triggers Claude AI analysis and, when warranted, creates an AIAlert + Notification.
"""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from app.models import User, RoleEnum, NotificationTypeEnum, AlertLevelEnum
from app.schemas import LessonRecordCreate, LessonRecordResponse
from app.security import get_current_user, get_teacher_user
from app.repositories import (
    LessonRecordRepository, ProgressMetricsRepository,
    AIAlertRepository, NotificationRepository, CourseRepository,
    UserRepository, AuditLogRepository,
)

router = APIRouter(prefix="/api/lesson-records", tags=["lesson-records"])


def _serialize(r) -> dict:
    diff = r.difficulty_level
    return {
        "id": str(r.id),
        "student_id": r.student_id,
        "course_id": r.course_id,
        "lesson_date": r.lesson_date,
        "attendance_status": r.attendance_status.value if hasattr(r.attendance_status, "value") else r.attendance_status,
        "grade_value": r.grade_value,
        "teacher_feedback": r.teacher_feedback,
        "difficulty_level": diff.value if hasattr(diff, "value") else diff,
        "engagement_rating": r.engagement_rating,
        "created_by_teacher_id": r.created_by_teacher_id,
        "created_at": r.created_at,
    }


@router.post("/", response_model=LessonRecordResponse, status_code=status.HTTP_201_CREATED)
async def create_lesson_record(
    body: LessonRecordCreate,
    current_user: User = Depends(get_teacher_user),
):
    course = await CourseRepository.get_by_id(body.course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    if course.teacher_id != str(current_user.id) and current_user.role != RoleEnum.ADMIN:
        raise HTTPException(status_code=403, detail="Not your course")

    record = await LessonRecordRepository.create(
        student_id=body.student_id,
        course_id=body.course_id,
        lesson_date=body.lesson_date,
        attendance_status=body.attendance_status,
        grade_value=body.grade_value,
        teacher_feedback=body.teacher_feedback,
        difficulty_level=body.difficulty_level,
        engagement_rating=body.engagement_rating,
        created_by_teacher_id=str(current_user.id),
    )

    await AuditLogRepository.log(
        user_id=str(current_user.id),
        action="create_lesson_record",
        resource_type="lesson_record",
        resource_id=str(record.id),
        details={"student_id": body.student_id, "course_id": body.course_id},
    )

    # Async AI analysis + score recompute (fire-and-forget, catches own errors)
    try:
        await _run_ai_analysis(body.student_id, body.course_id, str(record.id), course)
    except Exception:
        pass  # Never block the response

    try:
        from app.services.score_service import compute_and_save
        await compute_and_save(body.student_id, body.course_id)
    except Exception:
        pass  # Never block the response

    return LessonRecordResponse(**_serialize(record))


@router.get("/", response_model=List[LessonRecordResponse])
async def list_lesson_records(
    student_id: Optional[str] = None,
    course_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    """Teachers/admins can query any student; students/parents only see their own."""
    if current_user.role in [RoleEnum.TEACHER, RoleEnum.ADMIN]:
        target_student = student_id
    elif current_user.role == RoleEnum.STUDENT:
        if student_id and student_id != str(current_user.id):
            raise HTTPException(status_code=403, detail="Cannot view other students' records")
        target_student = str(current_user.id)
    elif current_user.role == RoleEnum.PARENT:
        if not student_id or student_id not in current_user.linked_student_ids:
            raise HTTPException(status_code=403, detail="Not linked to this student")
        target_student = student_id
    else:
        raise HTTPException(status_code=403, detail="Not authorized")

    if not target_student:
        return []

    records = await LessonRecordRepository.get_by_student_course(
        target_student, course_id or "", limit=100
    ) if course_id else await _get_all_records_for_student(target_student)

    return [LessonRecordResponse(**_serialize(r)) for r in records]


async def _get_all_records_for_student(student_id: str):
    """Fetch lesson records across all courses for a student."""
    from app.models import LessonRecord
    return await LessonRecord.find(
        LessonRecord.student_id == student_id
    ).sort(-LessonRecord.lesson_date).limit(100).to_list()


# ── AI analysis pipeline ──────────────────────────────────────────────────────

async def _run_ai_analysis(
    student_id: str, course_id: str, lesson_record_id: str, course
) -> None:
    from app.services.claude_service import analyze_student_progress
    from app.models import AttendanceStatusEnum

    records = await LessonRecordRepository.get_by_student_course(
        student_id, course_id, limit=20
    )
    if not records:
        return

    grades = [r.grade_value for r in records if r.grade_value is not None]
    total = len(records)
    present = sum(
        1 for r in records
        if (r.attendance_status.value if hasattr(r.attendance_status, "value") else r.attendance_status)
        in ("present", "late")
    )
    attendance_rate = (present / total * 100) if total else 0.0

    metrics = await ProgressMetricsRepository.get(student_id, course_id)
    trend = metrics.trend_direction if metrics else "stable"

    # Recalculate trend
    new_avg = sum(grades) / len(grades) if grades else 0.0
    if metrics:
        old_avg = metrics.average_grade
        if new_avg > old_avg + 3:
            trend = "improving"
        elif new_avg < old_avg - 3:
            trend = "declining"
        else:
            trend = "stable"

    await ProgressMetricsRepository.upsert(
        student_id=student_id,
        course_id=course_id,
        average_grade=new_avg,
        attendance_rate=attendance_rate,
        trend_direction=trend,
    )

    analysis = await analyze_student_progress(
        grades=grades,
        attendance_rate=attendance_rate,
        trend=trend,
        lesson_count=total,
    )

    alert_level_str = analysis.get("alert_level", "info")
    if alert_level_str not in ("warning", "critical"):
        return  # No alert needed for "info"

    level_enum = AlertLevelEnum.WARNING if alert_level_str == "warning" else AlertLevelEnum.CRITICAL

    ai_alert = await AIAlertRepository.create(
        student_id=student_id,
        course_id=course_id,
        alert_level=level_enum,
        message=analysis["explanation"],
        recommendation=analysis["recommended_action"],
        lesson_record_id=lesson_record_id,
        notification_sent=False,
    )

    # Notify the student
    msg = f"[{alert_level_str.upper()}] {analysis['explanation']} — {analysis['recommended_action']}"
    await NotificationRepository.create(
        user_id=student_id,
        message=msg,
        type=NotificationTypeEnum.AI_ALERT,
    )

    # Notify the teacher
    teacher = await UserRepository.get_by_id(course.teacher_id)
    if teacher:
        await NotificationRepository.create(
            user_id=str(teacher.id),
            message=f"AI Alert for student in {course.name}: {analysis['explanation']}",
            type=NotificationTypeEnum.AI_ALERT,
        )

    # High-severity email
    if alert_level_str == "critical":
        student = await UserRepository.get_by_id(student_id)
        if student:
            from app.services.email_service import EmailNotificationService
            EmailNotificationService.send_email(
                recipient=student.email,
                subject=f"Critical Academic Alert — {course.name}",
                html_content=(
                    f"<p>{analysis['explanation']}</p>"
                    f"<p><strong>Recommended action:</strong> {analysis['recommended_action']}</p>"
                ),
            )

    await AIAlertRepository.mark_notification_sent(str(ai_alert.id))
