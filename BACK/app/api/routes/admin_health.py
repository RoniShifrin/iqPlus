"""Admin System Health Panel API.

Provides aggregate activity indicators for administrators:
active users, lesson records, alerts triggered, emails delivered, etc.
Includes student listing endpoint for the admin dashboard Students tab.
"""
from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from app.models import User, RoleEnum
from app.repositories import UserRepository, EnrollmentRepository
from app.schemas import SystemHealthResponse
from app.security import get_current_user

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/system-health", response_model=SystemHealthResponse)
async def get_system_health(current_user: User = Depends(get_current_user)):
    if current_user.role != RoleEnum.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")

    from app.models import LessonRecord, AIAlert, WeeklySummary, AlertLevelEnum

    cutoff_7d = datetime.utcnow() - timedelta(days=7)

    # Active users — users created or updated in the past 30 days (proxy for activity)
    cutoff_30d = datetime.utcnow() - timedelta(days=30)
    active_users = await User.find(
        User.is_active == True,
        User.updated_at >= cutoff_30d,
    ).count()

    total_lesson_records = await LessonRecord.find_all().count()
    lesson_records_7d = await LessonRecord.find(
        LessonRecord.created_at >= cutoff_7d
    ).count()

    total_ai_alerts = await AIAlert.find_all().count()
    alerts_7d = await AIAlert.find(AIAlert.created_at >= cutoff_7d).count()

    critical_open = await AIAlert.find(
        AIAlert.alert_level == AlertLevelEnum.CRITICAL,
        AIAlert.parent_acknowledged == False,
    ).count()

    weekly_summaries_sent = await WeeklySummary.find(
        WeeklySummary.email_sent == True
    ).count()

    parent_ack_pending = await AIAlert.find(
        AIAlert.parent_acknowledged == False,
        AIAlert.notification_sent == True,
    ).count()

    return SystemHealthResponse(
        active_users=active_users,
        total_lesson_records=total_lesson_records,
        lesson_records_last_7_days=lesson_records_7d,
        total_ai_alerts=total_ai_alerts,
        alerts_last_7_days=alerts_7d,
        critical_alerts_open=critical_open,
        weekly_summaries_sent=weekly_summaries_sent,
        parent_acknowledgements_pending=parent_ack_pending,
    )


@router.get("/students")
async def list_admin_students(current_user: User = Depends(get_current_user)):
    """Return all student accounts with enrollment counts for the admin dashboard."""
    if current_user.role != RoleEnum.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")

    from app.models import Enrollment, EnrollmentStatusEnum

    # Fetch all three collections in parallel — no N+1
    from asyncio import gather
    students, all_enrollments, parents = await gather(
        User.find(User.role == RoleEnum.STUDENT).to_list(),
        Enrollment.find_all().to_list(),
        User.find(User.role == RoleEnum.PARENT).to_list(),
    )

    # Build enrollment counts per student_id
    enr_total: dict = {}
    enr_active: dict = {}
    for e in all_enrollments:
        sid = e.student_id
        enr_total[sid] = enr_total.get(sid, 0) + 1
        if e.status == EnrollmentStatusEnum.ACTIVE:
            enr_active[sid] = enr_active.get(sid, 0) + 1

    # Build set of student_ids that have a linked parent
    has_parent_set: set = set()
    for p in parents:
        for sid in (p.linked_student_ids or []):
            has_parent_set.add(sid)

    result = []
    for s in students:
        sid = str(s.id)
        display = s.display_name or f"{s.first_name or ''} {s.last_name or ''}".strip() or s.email
        result.append({
            "id": sid,
            "display_name": display,
            "first_name": s.first_name or "",
            "last_name": s.last_name or "",
            "email": s.email or "",
            "is_active": s.is_active,
            "enrollment_count": enr_total.get(sid, 0),
            "active_enrollment_count": enr_active.get(sid, 0),
            "has_parent": sid in has_parent_set,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        })
    return result
