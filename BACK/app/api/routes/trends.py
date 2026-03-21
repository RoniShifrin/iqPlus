"""Progress Trend Visualization API.

Converts historical lesson records into weekly time-series datasets
that dashboard chart components can consume directly.
"""
from collections import defaultdict
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.models import User, RoleEnum
from app.schemas import TrendDataset, TrendPoint
from app.security import get_current_user

router = APIRouter(prefix="/api/trends", tags=["trends"])


@router.get("/student/{student_id}", response_model=TrendDataset)
async def get_progress_trends(
    student_id: str,
    course_id: Optional[str] = Query(None),
    weeks: int = Query(12, ge=2, le=52),
    current_user: User = Depends(get_current_user),
):
    """Return weekly trend data points for charts.

    Access: teacher/admin (all), student (own), parent (linked).
    """
    _check_access(current_user, student_id)

    points = await _compute_weekly_points(student_id, course_id, weeks)
    direction = _detect_direction(points)

    return TrendDataset(
        student_id=student_id,
        course_id=course_id,
        direction=direction,
        points=points,
    )


# ── Access guard ──────────────────────────────────────────────────────────────

def _check_access(user: User, student_id: str) -> None:
    if user.role == RoleEnum.STUDENT:
        if str(user.id) != student_id:
            raise HTTPException(status_code=403, detail="Cannot view another student's trends")
    elif user.role == RoleEnum.PARENT:
        if student_id not in user.linked_student_ids:
            raise HTTPException(status_code=403, detail="Not linked to this student")


# ── Computation ───────────────────────────────────────────────────────────────

async def _compute_weekly_points(
    student_id: str, course_id: Optional[str], weeks: int
) -> List[TrendPoint]:
    from app.models import LessonRecord, AttendanceStatusEnum

    cutoff = datetime.utcnow() - timedelta(weeks=weeks)
    query = LessonRecord.find(
        LessonRecord.student_id == student_id,
        LessonRecord.lesson_date >= cutoff,
    )
    if course_id:
        query = LessonRecord.find(
            LessonRecord.student_id == student_id,
            LessonRecord.course_id == course_id,
            LessonRecord.lesson_date >= cutoff,
        )
    records = await query.sort(+LessonRecord.lesson_date).to_list()

    # Bucket records by ISO week
    buckets: dict[str, list] = defaultdict(list)
    for r in records:
        iso = r.lesson_date.isocalendar()
        key = f"{iso[0]}-W{iso[1]:02d}"
        buckets[key].append(r)

    # Build one TrendPoint per week, filling empty weeks with None
    # Generate all weeks from cutoff to now
    points: List[TrendPoint] = []
    current = cutoff
    while current <= datetime.utcnow():
        iso = current.isocalendar()
        key = f"{iso[0]}-W{iso[1]:02d}"
        week_records = buckets.get(key, [])

        grades = [r.grade_value for r in week_records if r.grade_value is not None]
        engagements = [r.engagement_rating for r in week_records if r.engagement_rating is not None]

        att_statuses = [
            r.attendance_status.value if hasattr(r.attendance_status, "value") else r.attendance_status
            for r in week_records
        ]
        present = sum(1 for s in att_statuses if s in ("present", "late"))
        att_rate = (present / len(att_statuses) * 100) if att_statuses else None

        points.append(TrendPoint(
            week_label=key,
            week_start=current,
            average_grade=round(sum(grades) / len(grades), 1) if grades else None,
            attendance_rate=round(att_rate, 1) if att_rate is not None else None,
            lesson_count=len(week_records),
            avg_engagement=round(sum(engagements) / len(engagements), 1) if engagements else None,
        ))
        current += timedelta(weeks=1)

    return points


def _detect_direction(points: List[TrendPoint]) -> str:
    """Classify overall trend as improving / declining / stable."""
    graded = [p for p in points if p.average_grade is not None]
    if len(graded) < 3:
        return "stable"

    first_half = graded[: len(graded) // 2]
    second_half = graded[len(graded) // 2 :]

    avg_first = sum(p.average_grade for p in first_half) / len(first_half)
    avg_second = sum(p.average_grade for p in second_half) / len(second_half)

    delta = avg_second - avg_first
    if delta > 4:
        return "improving"
    if delta < -4:
        return "declining"
    return "stable"
