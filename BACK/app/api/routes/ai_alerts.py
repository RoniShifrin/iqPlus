"""AI Alerts API routes.

Teachers/admins can list alerts for their courses.
Students can list their own alerts.
Parents can acknowledge alerts for their linked children.
"""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from app.models import User, RoleEnum, AIAlert
from app.schemas import AIAlertResponse, ParentAcknowledgeRequest
from app.security import get_current_user
from app.repositories import AIAlertRepository, CourseRepository

router = APIRouter(prefix="/api/ai-alerts", tags=["ai-alerts"])


def _serialize(a) -> dict:
    return {
        "id": str(a.id),
        "student_id": a.student_id,
        "course_id": a.course_id,
        "alert_level": a.alert_level.value if hasattr(a.alert_level, "value") else a.alert_level,
        "message": a.message,
        "recommendation": a.recommendation,
        "lesson_record_id": a.lesson_record_id,
        "notification_sent": a.notification_sent,
        "parent_seen": getattr(a, "parent_seen", False),
        "parent_acknowledged": getattr(a, "parent_acknowledged", False),
        "parent_acknowledged_at": getattr(a, "parent_acknowledged_at", None),
        "parent_comment": getattr(a, "parent_comment", None),
        "created_at": a.created_at,
    }


@router.get("/", response_model=List[AIAlertResponse])
async def list_ai_alerts(
    student_id: Optional[str] = None,
    course_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    if current_user.role == RoleEnum.STUDENT:
        # Students only see their own alerts
        sid = str(current_user.id)
        if course_id:
            alerts = await AIAlertRepository.list_by_student_course(sid, course_id)
        else:
            alerts = await AIAlertRepository.list_by_student(sid)
        return [AIAlertResponse(**_serialize(a)) for a in alerts]

    if current_user.role == RoleEnum.PARENT:
        if not student_id or student_id not in current_user.linked_student_ids:
            raise HTTPException(status_code=403, detail="Not linked to this student")
        if course_id:
            alerts = await AIAlertRepository.list_by_student_course(student_id, course_id)
        else:
            alerts = await AIAlertRepository.list_by_student(student_id)
        return [AIAlertResponse(**_serialize(a)) for a in alerts]

    # Teacher / Admin
    if course_id:
        if current_user.role == RoleEnum.TEACHER:
            course = await CourseRepository.get_by_id(course_id)
            if not course or course.teacher_id != str(current_user.id):
                raise HTTPException(status_code=403, detail="Not your course")
        alerts = await AIAlertRepository.list_by_course(course_id)
    elif student_id:
        alerts = await AIAlertRepository.list_by_student(student_id)
    elif current_user.role == RoleEnum.TEACHER:
        # Aggregate alerts across all courses owned by this teacher
        teacher_courses = await CourseRepository.list_by_teacher(str(current_user.id))
        alerts = []
        for tc in teacher_courses:
            alerts.extend(await AIAlertRepository.list_by_course(str(tc.id), limit=50))
        alerts.sort(key=lambda a: a.created_at, reverse=True)
        alerts = alerts[:100]
    else:
        if current_user.role != RoleEnum.ADMIN:
            raise HTTPException(status_code=400, detail="Provide course_id or student_id")
        alerts = await AIAlert.find_all().sort(-AIAlert.created_at).limit(100).to_list()

    return [AIAlertResponse(**_serialize(a)) for a in alerts]


@router.post("/{alert_id}/seen", response_model=AIAlertResponse)
async def mark_alert_seen(
    alert_id: str,
    current_user: User = Depends(get_current_user),
):
    """Parent marks the alert as seen (read)."""
    alert = await AIAlert.get(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    if current_user.role != RoleEnum.PARENT or alert.student_id not in current_user.linked_student_ids:
        raise HTTPException(status_code=403, detail="Not authorized")
    await alert.set({AIAlert.parent_seen: True})
    alert.parent_seen = True
    return AIAlertResponse(**_serialize(alert))


@router.post("/{alert_id}/acknowledge", response_model=AIAlertResponse)
async def acknowledge_alert(
    alert_id: str,
    body: ParentAcknowledgeRequest = None,
    current_user: User = Depends(get_current_user),
):
    """Parent formally acknowledges an AI alert for their child.
    An optional comment can be included in the request body.
    Teachers can see acknowledgement status and comment via the GET / list endpoint.
    """
    alert = await AIAlert.get(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    if current_user.role != RoleEnum.PARENT or alert.student_id not in current_user.linked_student_ids:
        raise HTTPException(status_code=403, detail="Only a linked parent can acknowledge this alert")
    updates: dict = {
        AIAlert.parent_seen: True,
        AIAlert.parent_acknowledged: True,
        AIAlert.parent_acknowledged_at: datetime.utcnow(),
    }
    if body and body.comment:
        updates[AIAlert.parent_comment] = body.comment
    await alert.set(updates)
    # Refresh local object so the response reflects the committed state
    alert.parent_seen = True
    alert.parent_acknowledged = True
    alert.parent_acknowledged_at = updates[AIAlert.parent_acknowledged_at]
    if body and body.comment:
        alert.parent_comment = body.comment
    return AIAlertResponse(**_serialize(alert))
