"""Progress and insights API routes"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

from app.models import User, RoleEnum, LearningInsight
from app.schemas import StudentProgressResponse, LearningInsightResponse
from app.security import get_current_user
from app.repositories import LearningInsightRepository, CourseRepository, UserRepository
from app.services import ProgressService, InsightService
from app.services.email_service import EmailNotificationService

router = APIRouter(prefix="/api/progress", tags=["progress"])


def _serialize_insight(i) -> dict:
    return {
        "id": str(i.id),
        "student_id": i.student_id,
        "course_id": i.course_id,
        "change_percentage": i.change_percentage,
        "insight_type": i.insight_type,
        "summary": i.summary,
        "metric_name": i.metric_name,
        "prev_value": i.prev_value,
        "curr_value": i.curr_value,
        "email_sent": i.email_sent,
        "created_at": i.created_at,
    }


@router.get("/student/{student_id}", response_model=StudentProgressResponse)
async def get_student_progress(
    student_id: str,
    course_id: str,
    current_user: User = Depends(get_current_user)
):
    is_own    = str(current_user.id) == student_id
    is_linked = current_user.role == RoleEnum.PARENT and student_id in (current_user.linked_student_ids or [])
    is_staff  = current_user.role in (RoleEnum.TEACHER, RoleEnum.ADMIN)
    if not (is_own or is_linked or is_staff):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    progress = await ProgressService.get_student_progress(student_id, course_id)
    insights = await LearningInsightRepository.list_by_student(student_id, limit=5)

    return StudentProgressResponse(
        student_id=student_id,
        course_id=course_id,
        average_grade=progress.get('average_grade', 0.0),
        attendance_rate=progress.get('attendance_rate', 0.0),
        last_grade_date=progress.get('last_grade_date'),
        last_attendance_date=progress.get('last_attendance_date'),
        recent_insights=[LearningInsightResponse(**_serialize_insight(i)) for i in insights]
    )


@router.get("/insights", response_model=List[LearningInsightResponse])
async def list_insights(
    current_user: User = Depends(get_current_user),
    student_id: str = None
):
    if student_id:
        is_own    = str(current_user.id) == student_id
        is_linked = current_user.role == RoleEnum.PARENT and student_id in (current_user.linked_student_ids or [])
        is_staff  = current_user.role in (RoleEnum.TEACHER, RoleEnum.ADMIN)
        if not (is_own or is_linked or is_staff):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        insights = await LearningInsightRepository.list_by_student(student_id)
        return [LearningInsightResponse(**_serialize_insight(i)) for i in insights]
    return []


@router.get("/insights/{insight_id}", response_model=LearningInsightResponse)
async def get_insight(
    insight_id: str,
    current_user: User = Depends(get_current_user)
):
    insight = await LearningInsight.get(insight_id)
    if not insight:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Insight not found")

    is_own    = str(current_user.id) == insight.student_id
    is_linked = current_user.role == RoleEnum.PARENT and insight.student_id in (current_user.linked_student_ids or [])
    is_staff  = current_user.role in (RoleEnum.TEACHER, RoleEnum.ADMIN)
    if not (is_own or is_linked or is_staff):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    return LearningInsightResponse(**_serialize_insight(insight))


@router.post("/insights/{insight_id}/send-notification", status_code=status.HTTP_200_OK)
async def send_insight_notification(
    insight_id: str,
    current_user: User = Depends(get_current_user)
):
    if current_user.role != RoleEnum.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can send notifications")

    insight = await LearningInsight.get(insight_id)
    if not insight:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Insight not found")

    student = await UserRepository.get_by_id(insight.student_id)
    course = await CourseRepository.get_by_id(insight.course_id)

    if not student or not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student or course not found")

    success = EmailNotificationService.send_insight_notification(
        recipient_email=student.email,
        student_name=f"{student.first_name} {student.last_name}",
        course_name=course.name,
        insight_summary=insight.summary,
        insight_type=insight.insight_type,
        recommendation="Review the insight above and consider seeking additional support if needed."
    )

    if success:
        await LearningInsightRepository.mark_sent(insight_id)
        return {"status": "sent"}

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Failed to send notification"
    )


@router.post("/generate-insights", status_code=status.HTTP_200_OK)
async def trigger_insight_generation(current_user: User = Depends(get_current_user)):
    if current_user.role != RoleEnum.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can trigger insight generation")

    from app.repositories import EnrollmentRepository

    students = await User.find(User.role == RoleEnum.STUDENT).to_list()
    insights_generated = 0

    for student in students:
        enrollments = await EnrollmentRepository.list_by_student(str(student.id))
        for enrollment in enrollments:
            grade_insight = await InsightService.check_and_generate_insights(str(student.id), enrollment.course_id)
            if grade_insight:
                insights_generated += 1

            attendance_insight = await InsightService.check_attendance_insights(str(student.id), enrollment.course_id)
            if attendance_insight:
                insights_generated += 1

    return {"status": "completed", "insights_generated": insights_generated}
