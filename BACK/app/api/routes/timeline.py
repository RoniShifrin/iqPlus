"""Student Learning Timeline API.

Aggregates lesson records, grades, attendance records, feedback, and AI alerts
into a single chronological timeline for each student.
"""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.models import User, RoleEnum
from app.schemas import TimelineEntry, TimelineResponse
from app.security import get_current_user

router = APIRouter(prefix="/api/timeline", tags=["timeline"])

ICON_MAP = {
    "lesson":     "📖",
    "grade":      "📊",
    "attendance": "✅",
    "feedback":   "💬",
    "alert":      "🚨",
}


@router.get("/{student_id}", response_model=TimelineResponse)
async def get_student_timeline(
    student_id: str,
    course_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
):
    """Return a unified chronological timeline for the given student."""
    _check_access(current_user, student_id)

    hide_private = current_user.role in (RoleEnum.STUDENT, RoleEnum.PARENT)
    entries = await _build_timeline(student_id, course_id, limit, hide_private=hide_private)
    return TimelineResponse(
        student_id=student_id,
        entries=entries,
        total=len(entries),
    )


# ── Access guard ──────────────────────────────────────────────────────────────

def _check_access(user: User, student_id: str) -> None:
    if user.role == RoleEnum.STUDENT:
        if str(user.id) != student_id:
            raise HTTPException(status_code=403, detail="Cannot view another student's timeline")
    elif user.role == RoleEnum.PARENT:
        if student_id not in user.linked_student_ids:
            raise HTTPException(status_code=403, detail="Not linked to this student")
    # Teacher / Admin: allowed for all students


# ── Timeline builder ─────────────────────────────────────────────────────────

async def _build_timeline(
    student_id: str, course_id: Optional[str], limit: int, hide_private: bool = False
) -> List[TimelineEntry]:
    from app.models import (
        LessonRecord, Grade, Attendance, Feedback, AIAlert, Course
    )

    # Pre-fetch course names to avoid N+1 lookups
    course_cache: dict[str, str] = {}

    async def course_name(cid: str) -> str:
        if cid not in course_cache:
            c = await Course.get(cid)
            course_cache[cid] = c.name if c else cid
        return course_cache[cid]

    entries: List[TimelineEntry] = []

    # ── 1. Lesson Records ──────────────────────────────────────────────────
    lr_query = LessonRecord.find(LessonRecord.student_id == student_id)
    if course_id:
        lr_query = LessonRecord.find(
            LessonRecord.student_id == student_id,
            LessonRecord.course_id == course_id,
        )
    lesson_records = await lr_query.sort(-LessonRecord.lesson_date).limit(limit).to_list()

    for r in lesson_records:
        att = r.attendance_status.value if hasattr(r.attendance_status, "value") else r.attendance_status
        grade_part = f" | Grade: {r.grade_value:.1f}%" if r.grade_value is not None else ""
        eng_part = f" | Engagement: {r.engagement_rating}/5" if r.engagement_rating else ""
        diff_part = f" | Difficulty: {r.difficulty_level}" if r.difficulty_level else ""
        cname = await course_name(r.course_id)
        entries.append(TimelineEntry(
            entry_type="lesson",
            timestamp=r.lesson_date,
            course_id=r.course_id,
            course_name=cname,
            summary=f"Lesson — {att.capitalize()}{grade_part}{eng_part}{diff_part}",
            detail=r.teacher_feedback,
            icon=ICON_MAP["lesson"],
        ))

    # ── 2. Standalone Grade Records ─────────────────────────────────────────
    grade_query = Grade.find(Grade.student_id == student_id)
    if course_id:
        grade_query = Grade.find(
            Grade.student_id == student_id, Grade.course_id == course_id
        )
    grades = await grade_query.sort(-Grade.recorded_at).limit(limit).to_list()

    for g in grades:
        cname = await course_name(g.course_id)
        entries.append(TimelineEntry(
            entry_type="grade",
            timestamp=g.recorded_at,
            course_id=g.course_id,
            course_name=cname,
            summary=f"Assessment recorded — {g.subject}: {g.score:.1f}%",
            icon=ICON_MAP["grade"],
        ))

    # ── 3. Standalone Attendance Records ────────────────────────────────────
    att_query = Attendance.find(Attendance.student_id == student_id)
    if course_id:
        att_query = Attendance.find(
            Attendance.student_id == student_id, Attendance.course_id == course_id
        )
    attendances = await att_query.sort(-Attendance.date).limit(limit).to_list()

    for a in attendances:
        status = a.status.value if hasattr(a.status, "value") else a.status
        cname = await course_name(a.course_id)
        entries.append(TimelineEntry(
            entry_type="attendance",
            timestamp=a.date,
            course_id=a.course_id,
            course_name=cname,
            summary=f"Attendance: {status.capitalize()}",
            detail=a.remarks,
            icon="✅" if status == "present" else "❌" if status == "absent" else "⏰",
        ))

    # ── 4. Teacher Feedback ─────────────────────────────────────────────────
    fb_query = Feedback.find(Feedback.student_id == student_id)
    if course_id:
        fb_query = Feedback.find(
            Feedback.student_id == student_id, Feedback.course_id == course_id
        )
    feedbacks = await fb_query.sort(-Feedback.submitted_at).limit(limit).to_list()

    for f in feedbacks:
        if hide_private:
            from app.models import FeedbackVisibilityEnum
            vis = f.visibility.value if hasattr(f.visibility, "value") else getattr(f, "visibility", "private")
            if vis != FeedbackVisibilityEnum.PUBLISHED.value:
                continue
        sentiment = f.sentiment.value if hasattr(f.sentiment, "value") else f.sentiment
        cname = await course_name(f.course_id)
        entries.append(TimelineEntry(
            entry_type="feedback",
            timestamp=f.submitted_at,
            course_id=f.course_id,
            course_name=cname,
            summary=f"Teacher feedback — {sentiment.capitalize()} sentiment",
            detail=f.content[:200] if f.content else None,
            icon=ICON_MAP["feedback"],
        ))

    # ── 5. AI Alerts ────────────────────────────────────────────────────────
    alert_query = AIAlert.find(AIAlert.student_id == student_id)
    if course_id:
        alert_query = AIAlert.find(
            AIAlert.student_id == student_id, AIAlert.course_id == course_id
        )
    alerts = await alert_query.sort(-AIAlert.created_at).limit(limit).to_list()

    for a in alerts:
        lvl = a.alert_level.value if hasattr(a.alert_level, "value") else a.alert_level
        if lvl == "critical":
            continue  # already very prominent in notification bell; omit from timeline noise
        cname = await course_name(a.course_id)
        entries.append(TimelineEntry(
            entry_type="alert",
            timestamp=a.created_at,
            course_id=a.course_id,
            course_name=cname,
            summary=f"AI Alert [{lvl.upper()}] — {a.message[:100]}",
            detail=a.recommendation,
            icon=ICON_MAP["alert"],
            severity=lvl,
        ))

    # Sort all entries descending by timestamp, apply limit
    entries.sort(key=lambda e: e.timestamp, reverse=True)
    return entries[:limit]
