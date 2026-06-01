"""AI Academic Intelligence — Planning, Recommendations, Workload Analysis, Risk Prediction.

All endpoints are read-only. No enrollments are created, no documents modified.

Endpoints:
  POST /api/planner/analyze           — analyze selected courses + full intelligence layer
  GET  /api/planner/recommendations   — AI course recommendations for a student

Data sources (read-only pre-computed collections):
  Course, Enrollment, PerformanceScore, ProgressPrediction,
  FeedbackAnalysis, AIAlert, Grade, Attendance
"""
import asyncio
import logging
from datetime import datetime, timedelta
from itertools import combinations as iter_combinations
from typing import List, Optional, Dict, Any

from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

from app.models import (
    Course, CourseStatusEnum, Enrollment, EnrollmentStatusEnum,
    PerformanceScore, ProgressPrediction, FeedbackAnalysis, AIAlert,
    RoleEnum, User, Grade, Attendance, AttendanceStatusEnum,
)
from app.security import get_current_user

router = APIRouter(prefix="/api/planner", tags=["academic-planning"])

# ── Pydantic schemas ─────────────────────────────────────────────────────────

class PlannerPreferences(BaseModel):
    preferred_days:      List[str]      = Field(default_factory=list)
    preferred_free_day:  Optional[str]  = None
    preferred_start_hour: Optional[float] = None   # e.g. 10.0 = prefer classes after 10:00
    preferred_end_hour:   Optional[float] = None   # e.g. 17.0 = prefer classes ending before 17:00
    max_courses:         int            = Field(default=5, ge=1, le=15)
    max_hours_per_day:   float          = Field(default=6.0, ge=0.5, le=24.0)
    avoid_early:         bool           = False
    avoid_late:          bool           = False

class PlannerRequest(BaseModel):
    course_ids:  List[str]          = Field(..., min_length=2, max_length=20)
    preferences: PlannerPreferences = Field(default_factory=PlannerPreferences)
    student_id:  Optional[str]      = None   # parent providing linked child id
    language:    str                = "en"


# ── Schedule math ─────────────────────────────────────────────────────────────

def _parse_h(t: str) -> float:
    """'HH:MM' → fractional hours."""
    try:
        h, m = t.split(":")
        return int(h) + int(m) / 60
    except Exception:
        return 0.0

def _duration(start: str, end: str) -> float:
    return max(0.0, _parse_h(end) - _parse_h(start))

def _courses_conflict(a: Course, b: Course) -> bool:
    sa, sb = a.schedule, b.schedule
    if not sa or not sb:
        return False
    if not set(sa.get("days", [])) & set(sb.get("days", [])):
        return False
    s_a, e_a = sa.get("start_time",""), sa.get("end_time","")
    s_b, e_b = sb.get("start_time",""), sb.get("end_time","")
    if not (s_a and e_a and s_b and e_b):
        return False
    return s_a < e_b and s_b < e_a

def _hours_per_day(courses: List[Course]) -> Dict[str, float]:
    totals: Dict[str, float] = {}
    for c in courses:
        s = c.schedule
        if not s:
            continue
        dur = _duration(s.get("start_time",""), s.get("end_time",""))
        for day in s.get("days", []):
            totals[day] = totals.get(day, 0.0) + dur
    return totals

def _weekly_hours(courses: List[Course]) -> float:
    return sum(_hours_per_day(courses).values())


# ── Student context fetching ─────────────────────────────────────────────────

async def _resolve_student_id(
    student_id: Optional[str],
    current_user: User,
) -> tuple[str, bool]:
    """
    Returns (resolved_student_id, is_parent).
    Raises 403/404 if parent tries to access an unlinked child.
    """
    role = current_user.role

    if role == RoleEnum.STUDENT:
        return str(current_user.id), False

    if role == RoleEnum.PARENT:
        linked = [str(x) for x in current_user.linked_student_ids]
        if student_id and student_id not in linked:
            raise HTTPException(403, "This student is not linked to your account.")
        sid = student_id or (linked[0] if linked else None)
        if not sid:
            raise HTTPException(400, "No linked students found on this account.")
        return sid, True

    if role == RoleEnum.ADMIN:
        if student_id:
            return student_id, False
        raise HTTPException(400, "Admin must provide student_id.")

    raise HTTPException(403, "Not authorized to use academic planner.")


async def _get_student_context(student_id: str) -> Dict[str, Any]:
    """
    Fetch pre-computed AI data for a student.
    Returns a context dict — never raises; falls back to empty values.
    """
    ctx: Dict[str, Any] = {
        "avg_score":          None,
        "scores":             {},       # course_id → PerformanceScore.score
        "classifications":    {},       # course_id → classification string
        "risk_levels":        {},       # course_id → risk_level string
        "predictions":        {},       # course_id → prediction_label
        "explanations":       {},       # course_id → ProgressPrediction.explanation
        "attendance_rate":    None,     # overall % present across all enrolled courses
        "feedback_sentiment": {},       # course_id → "positive"|"neutral"|"negative"
        "active_course_ids":  set(),    # currently active enrollment course ids
        "recent_alerts":      [],       # AIAlert messages
        "has_scores":         False,
        "has_predictions":    False,
        "has_alerts":         False,
        "workload_level":     "unknown",
    }

    try:
        # 1. Active enrollments
        enrollments = await Enrollment.find(
            Enrollment.student_id == student_id,
            Enrollment.status == EnrollmentStatusEnum.ACTIVE
        ).to_list()
        ctx["active_course_ids"] = {e.course_id for e in enrollments}

        # 2. PerformanceScores
        scores = await PerformanceScore.find(
            PerformanceScore.student_id == student_id
        ).to_list()
        if scores:
            ctx["has_scores"] = True
            for s in scores:
                ctx["scores"][s.course_id] = s.score
                ctx["classifications"][s.course_id] = s.classification
                # attendance_score is a 0-100 component; use it as proxy
                # We also keep grade_score and attendance_score for risk
                ctx.setdefault("attendance_scores", {})[s.course_id] = s.attendance_score
            all_scores = [s.score for s in scores]
            ctx["avg_score"] = sum(all_scores) / len(all_scores)

        # 3. ProgressPredictions
        preds = await ProgressPrediction.find(
            ProgressPrediction.student_id == student_id
        ).to_list()
        if preds:
            ctx["has_predictions"] = True
            for p in preds:
                ctx["risk_levels"][p.course_id] = p.risk_level
                ctx["predictions"][p.course_id] = p.prediction_label
                ctx["explanations"][p.course_id] = p.explanation

        # 4. Recent AIAlerts (30 days)
        cutoff = datetime.utcnow() - timedelta(days=30)
        alerts = await AIAlert.find(
            AIAlert.student_id == student_id,
            AIAlert.created_at >= cutoff,
        ).sort(-AIAlert.created_at).limit(5).to_list()
        if alerts:
            ctx["has_alerts"] = True
            ctx["recent_alerts"] = [
                {"level": a.alert_level, "message": a.message, "course_id": a.course_id}
                for a in alerts
            ]

        # 5. FeedbackAnalysis — last 60 days
        cutoff60 = datetime.utcnow() - timedelta(days=60)
        analyses = await FeedbackAnalysis.find(
            FeedbackAnalysis.student_id == student_id,
            FeedbackAnalysis.created_at >= cutoff60,
        ).sort(-FeedbackAnalysis.created_at).limit(30).to_list()
        for fa in analyses:
            if fa.course_id not in ctx["feedback_sentiment"]:
                ctx["feedback_sentiment"][fa.course_id] = fa.sentiment_label

        # 6. Workload level based on active enrollments
        n = len(ctx["active_course_ids"])
        if n == 0:
            ctx["workload_level"] = "light"
        elif n <= 2:
            ctx["workload_level"] = "moderate"
        elif n <= 4:
            ctx["workload_level"] = "heavy"
        else:
            ctx["workload_level"] = "very_heavy"

    except asyncio.CancelledError:
        raise  # never suppress cancellation
    except Exception:
        pass  # gracefully degrade — context remains empty

    return ctx


# ── Workload analysis ─────────────────────────────────────────────────────────

def _analyze_workload(
    courses: List[Course],
    prefs: PlannerPreferences,
    student_ctx: Dict[str, Any],
    language: str = "en",
) -> Dict[str, Any]:
    """Return detailed per-day and weekly workload analysis."""
    day_map: Dict[str, List[Dict]] = {}
    for c in courses:
        s = c.schedule
        if not s:
            continue
        start_h = _parse_h(s.get("start_time",""))
        end_h   = _parse_h(s.get("end_time",""))
        dur     = max(0.0, end_h - start_h)
        for day in s.get("days", []):
            day_map.setdefault(day, []).append({
                "name":    c.name,
                "start_h": start_h,
                "end_h":   end_h,
                "dur":     dur,
            })

    weekly_hours = 0.0
    days_detail: Dict[str, Any] = {}
    overloaded_days: List[str] = []

    for day, slots in day_map.items():
        slots.sort(key=lambda x: x["start_h"])
        day_hours = sum(sl["dur"] for sl in slots)
        weekly_hours += day_hours

        # Detect consecutive blocks with < 30 min break between them
        consecutive_blocks = 0
        for i in range(1, len(slots)):
            gap_h = slots[i]["start_h"] - slots[i-1]["end_h"]
            if gap_h < 0.5:   # less than 30 minutes
                consecutive_blocks += 1

        if day_hours > prefs.max_hours_per_day:
            pressure = "heavy"
            overloaded_days.append(day)
        elif day_hours > prefs.max_hours_per_day * 0.6:
            pressure = "moderate"
        else:
            pressure = "light"

        days_detail[day] = {
            "hours":              round(day_hours, 1),
            "courses":            len(slots),
            "consecutive_blocks": consecutive_blocks,
            "pressure":           pressure,
            "slots":              [{"name": sl["name"], "time": f"{_fmt_h(sl['start_h'])}-{_fmt_h(sl['end_h'])}"} for sl in slots],
        }

    # Preferred free day check
    free_day_respected = (
        prefs.preferred_free_day not in day_map
        if prefs.preferred_free_day else True
    )

    # Overall pressure
    if weekly_hours == 0:
        pressure_level = "unknown"
    elif weekly_hours < 10:
        pressure_level = "light"
    elif weekly_hours < 20:
        pressure_level = "moderate"
    else:
        pressure_level = "heavy"

    # Combine with existing workload
    existing_load = student_ctx.get("workload_level", "unknown")

    from app.services.ai_messages import msg as _msg
    # Summary text
    parts = []
    if weekly_hours > 0:
        parts.append(_msg("pl.wl.adds_hours", language, h=weekly_hours, days=len(day_map)))
    if overloaded_days:
        overload_key = "pl.wl.overloaded_one" if len(overloaded_days) == 1 else "pl.wl.overloaded_many"
        parts.append(_msg(overload_key, language, max_h=prefs.max_hours_per_day, days_list=", ".join(overloaded_days)))
    elif weekly_hours > 0:
        parts.append(_msg("pl.wl.within_limit", language))
    if prefs.preferred_free_day:
        if free_day_respected:
            parts.append(_msg("pl.wl.free_day_ok", language, day=prefs.preferred_free_day))
        else:
            parts.append(_msg("pl.wl.free_day_no", language, day=prefs.preferred_free_day))
    if existing_load in ("heavy", "very_heavy") and len(courses) >= 3:
        parts.append(_msg("pl.wl.heavy_combo", language))

    return {
        "weekly_hours":       round(weekly_hours, 1),
        "pressure_level":     pressure_level,
        "days":               days_detail,
        "overloaded_days":    overloaded_days,
        "free_day_respected": free_day_respected,
        "balanced":           len(overloaded_days) == 0,
        "summary_text":       " ".join(parts) or _msg("pl.wl.no_data", language),
    }

def _fmt_h(h: float) -> str:
    """9.5 → '09:30'"""
    hh = int(h)
    mm = int(round((h - hh) * 60))
    return f"{hh:02d}:{mm:02d}"


# ── Risk prediction ────────────────────────────────────────────────────────────

def _predict_risks(
    courses: List[Course],
    student_ctx: Dict[str, Any],
    prefs: PlannerPreferences,
    workload: Dict[str, Any],
    language: str = "en",
) -> List[Dict[str, Any]]:
    """Generate risk warnings from student context + selected schedule."""
    from app.services.ai_messages import msg as _msg
    warnings: List[Dict[str, Any]] = []

    avg_score = student_ctx.get("avg_score")
    risk_levels = student_ctx.get("risk_levels", {})
    recent_alerts = student_ctx.get("recent_alerts", [])
    workload_level = student_ctx.get("workload_level", "unknown")
    active_count = len(student_ctx.get("active_course_ids", set()))

    if active_count + len(courses) > prefs.max_courses + 2:
        warnings.append({
            "severity": "warning",
            "course_id": None,
            "message": _msg("pl.risk.too_many", language, new=len(courses), existing=active_count),
        })

    if avg_score is not None and avg_score < 60:
        warnings.append({
            "severity": "warning",
            "course_id": None,
            "message": _msg("pl.risk.low_avg", language, avg=avg_score),
        })

    high_risk = [cid for cid, lvl in risk_levels.items() if lvl in ("high",)]
    medium_risk = [cid for cid, lvl in risk_levels.items() if lvl == "medium"]
    if high_risk:
        warnings.append({
            "severity": "critical",
            "course_id": None,
            "message": _msg("pl.risk.high_risk_enrolled", language, n=len(high_risk)),
        })
    elif medium_risk:
        warnings.append({
            "severity": "warning",
            "course_id": None,
            "message": _msg("pl.risk.medium_risk_enrolled", language, n=len(medium_risk)),
        })

    critical_alerts = [a for a in recent_alerts if a.get("level") == "critical"]
    if critical_alerts:
        warnings.append({
            "severity": "critical",
            "course_id": critical_alerts[0].get("course_id"),
            "message": _msg("pl.risk.critical_alert", language, alert_msg=critical_alerts[0]["message"][:120]),
        })
    elif recent_alerts:
        warnings.append({
            "severity": "info",
            "course_id": None,
            "message": _msg("pl.risk.recent_alerts", language),
        })

    for day in workload.get("overloaded_days", []):
        info = workload["days"].get(day, {})
        warnings.append({
            "severity": "warning",
            "course_id": None,
            "message": _msg("pl.risk.day_overloaded", language, day=day, hours=info.get("hours", 0), max_h=prefs.max_hours_per_day),
        })

    for day, info in workload.get("days", {}).items():
        if info.get("consecutive_blocks", 0) >= 2:
            warnings.append({
                "severity": "info",
                "course_id": None,
                "message": _msg("pl.risk.consecutive", language, day=day, blocks=info["consecutive_blocks"]),
            })

    if workload_level == "very_heavy":
        warnings.append({
            "severity": "warning",
            "course_id": None,
            "message": _msg("pl.risk.very_heavy", language),
        })

    no_schedule = [c.name for c in courses if not c.schedule]
    if no_schedule:
        warnings.append({
            "severity": "info",
            "course_id": None,
            "message": _msg("pl.risk.no_schedule", language, courses=", ".join(no_schedule)),
        })

    return warnings


# ── Scoring ───────────────────────────────────────────────────────────────────

def _score_combination(
    courses: List[Course],
    prefs: PlannerPreferences,
    student_ctx: Dict[str, Any],
) -> float:
    score = 50.0
    preferred = set(prefs.preferred_days)
    free_day = prefs.preferred_free_day

    for c in courses:
        s = c.schedule
        if not s:
            continue
        days     = s.get("days", [])
        start_h  = _parse_h(s.get("start_time","08:00"))
        end_h    = _parse_h(s.get("end_time","09:00"))

        if preferred:
            score += len(set(days) & preferred) * 4

        if prefs.preferred_start_hour and start_h >= prefs.preferred_start_hour:
            score += 5
        elif prefs.preferred_start_hour and start_h < prefs.preferred_start_hour:
            score -= 5

        if prefs.preferred_end_hour and end_h <= prefs.preferred_end_hour:
            score += 5
        elif prefs.preferred_end_hour and end_h > prefs.preferred_end_hour:
            score -= 5

        if prefs.avoid_early and start_h < 9.0:
            score -= 12
        if prefs.avoid_late and end_h > 20.0:
            score -= 12

        if free_day and free_day in days:
            score -= 15  # using preferred free day is penalized

    # Daily hours penalty
    hpd = _hours_per_day(courses)
    for day, hrs in hpd.items():
        if hrs > prefs.max_hours_per_day:
            score -= (hrs - prefs.max_hours_per_day) * 6

    # Academic fit bonus — if we have performance data, prefer courses
    # where student historically performs well (proxy: their avg score)
    avg = student_ctx.get("avg_score")
    if avg is not None:
        if avg >= 75:
            score += 8    # good performer can handle more courses
        elif avg < 55:
            score -= 8    # struggling student — fewer is better, so penalize larger combos
            if len(courses) > 3:
                score -= 6

    return max(0.0, min(100.0, score))


# ── Explanation layer ─────────────────────────────────────────────────────────

def _personalization_level(student_ctx: Dict[str, Any]) -> str:
    if student_ctx.get("has_scores") and student_ctx.get("has_predictions"):
        return "full"
    if student_ctx.get("has_scores") or student_ctx.get("has_alerts"):
        return "partial"
    return "schedule_only"

def _explain_combination(
    courses: List[Course],
    score: float,
    prefs: PlannerPreferences,
    rank: int,
    student_ctx: Dict[str, Any],
    workload: Dict[str, Any],
    risks: List[Dict],
    language: str = "en",
) -> str:
    names = [c.name for c in courses]
    preferred = set(prefs.preferred_days)
    days_covered: set = set()
    for c in courses:
        s = c.schedule or {}
        days_covered.update(s.get("days", []))

    matched = days_covered & preferred if preferred else set()
    level = _personalization_level(student_ctx)
    avg = student_ctx.get("avg_score")
    critical = [r for r in risks if r["severity"] == "critical"]
    weekly_h = workload.get("weekly_hours", 0)

    from app.services.ai_messages import msg as _msg
    parts: List[str] = []

    if rank == 1:
        parts.append(_msg("pl.exp.rank1_high" if score >= 70 else "pl.exp.rank1_low", language))
    elif rank == 2:
        parts.append(_msg("pl.exp.rank2", language))
    else:
        parts.append(_msg("pl.exp.rank_other", language))

    if len(names) == 1:
        parts.append(_msg("pl.exp.one_course", language, name=names[0]))
    else:
        parts.append(_msg("pl.exp.multi_courses", language, n=len(names), names=", ".join(names)))

    if matched:
        parts.append(_msg("pl.exp.preferred_days", language, days=", ".join(sorted(matched))))
    if prefs.preferred_free_day and prefs.preferred_free_day not in days_covered:
        parts.append(_msg("pl.exp.free_day_ok", language, day=prefs.preferred_free_day))

    if weekly_h > 0:
        if workload["balanced"]:
            parts.append(_msg("pl.exp.workload_balanced", language, h=weekly_h, days=len(workload["days"])))
        else:
            bad = workload.get("overloaded_days", [])
            parts.append(_msg("pl.exp.workload_overload", language, h=weekly_h, overloaded=", ".join(bad)))

    if level == "full" and avg is not None:
        if avg >= 80:
            parts.append(_msg("pl.exp.academic_strong", language, avg=avg))
        elif avg >= 65:
            parts.append(_msg("pl.exp.academic_good", language, avg=avg))
        else:
            parts.append(_msg("pl.exp.academic_low", language, avg=avg))
    elif level == "partial":
        parts.append(_msg("pl.exp.partial_ctx", language))
    else:
        parts.append(_msg("pl.exp.schedule_only", language))

    if critical:
        parts.append(_msg("pl.exp.critical_risk", language))

    return " ".join(parts)


# ── Course recommendation engine ─────────────────────────────────────────────

async def _compute_recommendations(
    student_id: str,
    all_courses: List[Course],
    active_course_ids: set,
    student_ctx: Dict[str, Any],
    prefs: PlannerPreferences,
    language: str = "en",
) -> List[Dict[str, Any]]:
    """
    For each published course not yet enrolled, compute a fit score and reasons.
    Returns up to 5 recommendations, sorted by fit score.
    """
    # Batch-load all enrolled courses at once instead of N individual queries
    from bson.errors import InvalidId as _InvalidId
    from beanie import PydanticObjectId as _POID
    enrolled_courses: List[Course] = []
    if active_course_ids:
        valid_oids = []
        for cid in active_course_ids:
            try:
                valid_oids.append(_POID(cid))
            except (_InvalidId, Exception):
                pass
        if valid_oids:
            enrolled_courses = await Course.find({"_id": {"$in": valid_oids}}).to_list()

    existing_hpd = _hours_per_day(enrolled_courses)
    avg = student_ctx.get("avg_score")
    risk_levels = student_ctx.get("risk_levels", {})
    feedback_sent = student_ctx.get("feedback_sentiment", {})
    level = _personalization_level(student_ctx)

    scored: List[Dict] = []

    from app.services.ai_messages import msg as _msg

    for course in all_courses:
        cid = str(course.id)
        if cid in active_course_ids:
            continue   # already enrolled

        reasons: List[str] = []
        warnings: List[str] = []
        fit_score = 50.0

        has_conflict = any(_courses_conflict(course, ec) for ec in enrolled_courses)
        if has_conflict:
            fit_score -= 40
            warnings.append(_msg("pl.rec.conflict", language))
        else:
            fit_score += 20
            reasons.append(_msg("pl.rec.no_conflict", language))

        s = course.schedule or {}
        course_days = set(s.get("days", []))
        if prefs.preferred_days:
            matched = course_days & set(prefs.preferred_days)
            if matched:
                fit_score += 10
                reasons.append(_msg("pl.rec.preferred_days", language, days=", ".join(sorted(matched))))
        if prefs.preferred_free_day and prefs.preferred_free_day in course_days:
            fit_score -= 10
            warnings.append(_msg("pl.rec.free_day_used", language, day=prefs.preferred_free_day))

        start_h = _parse_h(s.get("start_time",""))
        end_h   = _parse_h(s.get("end_time",""))
        if prefs.avoid_early and start_h > 0 and start_h < 9.0:
            fit_score -= 12
            warnings.append(_msg("pl.rec.too_early", language))
        if prefs.avoid_late and end_h > 0 and end_h > 20.0:
            fit_score -= 12
            warnings.append(_msg("pl.rec.too_late", language))

        dur = _duration(s.get("start_time",""), s.get("end_time",""))
        for day in course_days:
            new_day_total = existing_hpd.get(day, 0) + dur
            if new_day_total > prefs.max_hours_per_day:
                fit_score -= 8
                warnings.append(_msg("pl.rec.day_overloaded", language, day=day, max_h=prefs.max_hours_per_day))
                break
        else:
            if dur > 0:
                reasons.append(_msg("pl.rec.fits_limit", language, dur=dur))

        if level in ("full", "partial") and avg is not None:
            high_risk_count = sum(1 for lvl in risk_levels.values() if lvl == "high")
            if high_risk_count >= 2:
                fit_score -= 15
                warnings.append(_msg("pl.rec.high_risk_multi", language))
            elif avg >= 75:
                fit_score += 10
                reasons.append(_msg("pl.rec.strong_avg", language, avg=avg))
            elif avg < 55:
                fit_score -= 8
                warnings.append(_msg("pl.rec.low_avg", language))

            sent = feedback_sent.get(cid)
            if sent == "positive":
                fit_score += 8
                reasons.append(_msg("pl.rec.pos_feedback", language))
            elif sent == "negative":
                fit_score -= 10
                warnings.append(_msg("pl.rec.neg_feedback", language))

        if not reasons:
            reasons.append(_msg("pl.rec.schedule_fit", language))

        # Category
        if fit_score >= 70:
            category = "great_fit"
        elif fit_score >= 50:
            category = "good_fit"
        elif fit_score >= 30:
            category = "possible"
        else:
            category = "not_recommended"

        scored.append({
            "course": {
                "id":         cid,
                "name":       course.name,
                "code":       course.code,
                "schedule":   course.schedule,
                "teacher_id": course.teacher_id,
                "status":     course.status,
            },
            "fit_score":    round(max(0.0, min(100.0, fit_score)), 1),
            "reasons":      reasons,
            "warnings":     warnings,
            "schedule_fit": "no_conflict" if not has_conflict else "has_conflict",
            "category":     category,
        })

    scored.sort(key=lambda x: x["fit_score"], reverse=True)
    return scored[:5]


# ── Main analysis endpoint ────────────────────────────────────────────────────

@router.post("/analyze")
async def analyze_schedule(
    body: PlannerRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Analyze selected courses and return:
    - Ranked schedule combinations
    - Workload analysis
    - Risk warnings
    - Personalized AI explanation
    """
    try:
        return await _analyze_schedule_inner(body, current_user)
    except HTTPException:
        raise
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.exception("Unexpected error in analyze_schedule: %s", exc)
        raise HTTPException(status_code=500, detail="An unexpected error occurred. Please try again.") from exc


async def _analyze_schedule_inner(body: PlannerRequest, current_user: User):
    from app.services.ai_messages import msg as _msg
    student_id, is_parent = await _resolve_student_id(body.student_id, current_user)
    prefs = body.preferences
    language = body.language or "en"

    # Fetch requested courses (published only)
    courses: List[Course] = []
    invalid_ids: List[str] = []
    for cid in body.course_ids:
        try:
            c = await Course.get(cid)
        except (InvalidId, Exception) as e:
            logger.warning("Skipping course_id %r: %s", cid, e)
            invalid_ids.append(cid)
            continue
        if c and c.status == CourseStatusEnum.PUBLISHED and not getattr(c, "deleted_at", None):
            courses.append(c)

    if len(courses) < 2:
        detail = _msg("pl.msg.not_enough", language)
        if invalid_ids:
            detail += _msg("pl.msg.invalid_ids", language, n=len(invalid_ids))
        return {
            "combinations": [], "total_valid": 0, "selected_count": len(courses),
            "conflicts": [], "global_workload": None, "global_risk_warnings": [],
            "personalization_level": "schedule_only",
            "message": detail,
        }

    # Fetch student context
    student_ctx = await _get_student_context(student_id)
    p_level = _personalization_level(student_ctx)

    # Build conflict pairs
    conflict_pairs: set = set()
    for i in range(len(courses)):
        for j in range(i + 1, len(courses)):
            if _courses_conflict(courses[i], courses[j]):
                conflict_pairs.add((i, j))

    max_n = min(prefs.max_courses, len(courses))

    # Enumerate valid non-conflicting subsets
    valid_combos: List[List[Course]] = []
    for size in range(2, max_n + 1):
        for idx_combo in iter_combinations(range(len(courses)), size):
            ok = all(
                (a, b) not in conflict_pairs
                for a, b in iter_combinations(idx_combo, 2)
            )
            if ok:
                valid_combos.append([courses[i] for i in idx_combo])
        if len(valid_combos) > 200:
            break

    # Build conflict report
    all_conflicts = []
    for a, b in conflict_pairs:
        ca, cb = courses[a], courses[b]
        sa, sb = ca.schedule or {}, cb.schedule or {}
        all_conflicts.append({
            "course_a": {"id": str(ca.id), "name": ca.name},
            "course_b": {"id": str(cb.id), "name": cb.name},
            "shared_days": list(set(sa.get("days",[])) & set(sb.get("days",[]))),
            "time_a": f"{sa.get('start_time','')}-{sa.get('end_time','')}",
            "time_b": f"{sb.get('start_time','')}-{sb.get('end_time','')}",
        })

    if not valid_combos:
        workload = _analyze_workload(courses, prefs, student_ctx, language)
        risks    = _predict_risks(courses, student_ctx, prefs, workload, language)
        return {
            "combinations": [],
            "total_valid": 0,
            "selected_count": len(courses),
            "conflicts": all_conflicts,
            "global_workload": workload,
            "global_risk_warnings": risks,
            "personalization_level": p_level,
            "message": _msg("pl.msg.all_conflict", language),
        }

    # Score + rank
    scored = sorted(
        valid_combos,
        key=lambda c: (len(c), _score_combination(c, prefs, student_ctx)),
        reverse=True,
    )
    seen: set = set()
    top3: List[List[Course]] = []
    for combo in scored:
        key = frozenset(str(c.id) for c in combo)
        if key not in seen:
            seen.add(key)
            top3.append(combo)
        if len(top3) >= 3:
            break

    # Build result combos
    result_combos = []
    for rank, combo in enumerate(top3, 1):
        score    = _score_combination(combo, prefs, student_ctx)
        workload = _analyze_workload(combo, prefs, student_ctx, language)
        risks    = _predict_risks(combo, student_ctx, prefs, workload, language)
        expl     = _explain_combination(combo, score, prefs, rank, student_ctx, workload, risks, language)
        combo_ids = {str(c.id) for c in combo}

        result_combos.append({
            "rank":         rank,
            "score":        round(score, 1),
            "explanation":  expl,
            "courses": [
                {
                    "id": str(c.id), "name": c.name, "code": c.code,
                    "schedule": c.schedule, "teacher_id": c.teacher_id,
                }
                for c in combo
            ],
            "excluded_courses": [
                {"id": str(c.id), "name": c.name}
                for c in courses if str(c.id) not in combo_ids
            ],
            "workload_summary": workload,
            "risk_warnings":    risks,
            "hours_per_day":    _hours_per_day(combo),
        })

    # Overall workload + risks for full selection (for the global summary panel)
    global_workload = _analyze_workload(top3[0] if top3 else courses, prefs, student_ctx, language)
    global_risks    = _predict_risks(top3[0] if top3 else courses, student_ctx, prefs, global_workload, language)

    msg_key = "pl.msg.found_full" if p_level == "full" else "pl.msg.found_other"
    msg = _msg(msg_key, language, total=len(valid_combos), top=len(result_combos))

    return {
        "combinations":         result_combos,
        "total_valid":          len(valid_combos),
        "selected_count":       len(courses),
        "conflicts":            all_conflicts,
        "global_workload":      global_workload,
        "global_risk_warnings": global_risks,
        "personalization_level": p_level,
        "message":              msg,
    }


# ── Recommendations endpoint ──────────────────────────────────────────────────

@router.get("/recommendations")
async def get_recommendations(
    student_id:    Optional[str] = Query(default=None),
    avoid_early:   bool          = Query(default=False),
    avoid_late:    bool          = Query(default=False),
    max_hours_day: float         = Query(default=6.0, ge=0.5, le=24.0),
    language:      str           = Query(default="en"),
    current_user:  User          = Depends(get_current_user),
):
    """
    Return AI-ranked course recommendations for a student.
    Considers: schedule fit, workload balance, academic performance, preferences.
    """
    try:
        sid, _ = await _resolve_student_id(student_id, current_user)

        prefs = PlannerPreferences(
            avoid_early=avoid_early,
            avoid_late=avoid_late,
            max_hours_per_day=max_hours_day,
        )

        # All published courses
        all_courses = await Course.find(
            Course.status == CourseStatusEnum.PUBLISHED,
        ).to_list()

        student_ctx = await _get_student_context(sid)
        active_ids  = student_ctx.get("active_course_ids", set())
        p_level     = _personalization_level(student_ctx)

        recs = await _compute_recommendations(
            student_id=sid,
            all_courses=all_courses,
            active_course_ids=active_ids,
            student_ctx=student_ctx,
            prefs=prefs,
            language=language,
        )

        from app.services.ai_messages import msg as _msg
        if p_level == "schedule_only":
            msg = _msg("pl.msg.recs_schedule_only", language)
        elif p_level == "partial":
            msg = _msg("pl.msg.recs_partial", language)
        else:
            msg = _msg("pl.msg.recs_full", language)

        return {
            "recommendations":     recs,
            "enrolled_course_ids": list(active_ids),
            "personalization_level": p_level,
            "message": msg,
        }
    except HTTPException:
        raise
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.exception("Unexpected error in get_recommendations: %s", exc)
        raise HTTPException(status_code=500, detail="An unexpected error occurred. Please try again.") from exc
