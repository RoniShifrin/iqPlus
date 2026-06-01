"""AI Intelligence Layer — read-only analytics derived from existing AI collections.

All endpoints read from pre-computed documents:
  ProgressPrediction  → risk_level, prediction_label, explanation, recommendation
  PerformanceScore    → score, classification
  FeedbackAnalysis    → sentiment_label, extracted_tags
  LearningInsight     → insight_type, summary
  AIAlert             → alert_level, message

No original academic records are modified. No expensive recomputation at query time.
"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.models import (
    User, RoleEnum, ProgressPrediction, PerformanceScore,
    FeedbackAnalysis, LearningInsight, AIAlert, Enrollment,
    EnrollmentStatusEnum, Course, CourseStatusEnum,
)
from app.security import get_current_user
from app.repositories import (
    CourseRepository, EnrollmentRepository,
    PerformanceScoreRepository, ProgressPredictionRepository,
    AIAlertRepository, UserRepository,
)

router = APIRouter(prefix="/api/ai", tags=["ai-insights"])

# ── 0. Feedback trend for a course ─────────────────────────────────────────────

@router.get("/feedback-trend/{course_id}")
async def get_feedback_trend(
    course_id: str,
    days: int = 60,
    language: str = Query(default="en"),
    current_user: User = Depends(get_current_user),
):
    """Aggregated feedback sentiment and tag-frequency trend for a course.

    Returns sentiment distribution, top extracted tags, and a period-over-period
    trend direction.  Teachers: own course only.  Admins: any course.
    Reads FeedbackAnalysis cache only — no recomputation.
    """
    if current_user.role not in (RoleEnum.TEACHER, RoleEnum.ADMIN):
        raise HTTPException(status_code=403, detail="Not authorized")

    course = await CourseRepository.get_by_id(course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    if current_user.role == RoleEnum.TEACHER and course.teacher_id != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not your course")

    cutoff = datetime.utcnow() - timedelta(days=days)
    analyses = await FeedbackAnalysis.find(
        FeedbackAnalysis.course_id == course_id,
        FeedbackAnalysis.created_at >= cutoff,
    ).sort(-FeedbackAnalysis.created_at).to_list()

    from app.services.ai_messages import msg as _msg
    if not analyses:
        return {
            "course_id":              course_id,
            "period_days":            days,
            "total_feedback":         0,
            "sentiment_distribution": {},
            "top_tags":               [],
            "concern_summary":        _msg("fbt.no_data", language),
            "trend":                  "stable",
        }

    total = len(analyses)

    # Sentiment distribution
    sentiment_counts: dict = {"positive": 0, "neutral": 0, "negative": 0}
    for a in analyses:
        lbl = a.sentiment_label if a.sentiment_label in sentiment_counts else "neutral"
        sentiment_counts[lbl] += 1
    sentiment_pct = {k: round(v / total * 100) for k, v in sentiment_counts.items()}

    # Tag frequency
    tag_freq: dict = {}
    for a in analyses:
        for tag in (a.extracted_tags or []):
            tag_freq[tag] = tag_freq.get(tag, 0) + 1
    top_tags = [
        {"tag": t, "count": c}
        for t, c in sorted(tag_freq.items(), key=lambda x: x[1], reverse=True)[:6]
    ]

    # Period-over-period trend: compare recent half vs older half
    mid = total // 2
    trend = "stable"
    if mid > 0:
        recent_neg = sum(1 for a in analyses[:mid] if a.sentiment_label == "negative") / mid
        older_neg  = sum(1 for a in analyses[mid:] if a.sentiment_label == "negative") / (total - mid)
        if recent_neg - older_neg > 0.15:
            trend = "worsening"
        elif older_neg - recent_neg > 0.15:
            trend = "improving"

    # Concern summary sentence
    neg_pct = sentiment_pct.get("negative", 0)
    pos_pct = sentiment_pct.get("positive", 0)
    parts: list[str] = []
    if neg_pct >= 50:
        parts.append(_msg("fbt.neg_over_half", language, neg_pct=neg_pct))
    elif neg_pct >= 30:
        parts.append(_msg("fbt.neg_moderate", language, neg_pct=neg_pct))
    elif pos_pct >= 60:
        parts.append(_msg("fbt.pos_majority", language, pos_pct=pos_pct))
    else:
        parts.append(_msg("fbt.mixed", language))

    concern_tags = [t["tag"] for t in top_tags
                    if t["tag"] in ("participation", "homework", "behavior", "understanding", "consistency")]
    if concern_tags:
        parts.append(_msg("fbt.recurring_areas", language, areas=", ".join(concern_tags[:3])))

    if trend == "worsening":
        parts.append(_msg("fbt.trend_worsening", language))
    elif trend == "improving":
        parts.append(_msg("fbt.trend_improving", language))

    return {
        "course_id":              course_id,
        "period_days":            days,
        "total_feedback":         total,
        "sentiment_distribution": sentiment_pct,
        "top_tags":               top_tags,
        "concern_summary":        " ".join(parts),
        "trend":                  trend,
    }

# ── helpers ────────────────────────────────────────────────────────────────────

_RISK_ORDER = {"high": 0, "medium": 1, "low": 2}

def _safe_risk(risk: Optional[str]) -> str:
    return risk if risk in ("high", "medium", "low") else "low"


async def _student_risk_entry(student_id: str, course_id: str) -> dict:
    """Single enrollment risk snapshot — reads cached docs only."""
    pred  = await ProgressPredictionRepository.get(student_id, course_id)
    score = await PerformanceScoreRepository.get(student_id, course_id)

    risk_level        = _safe_risk(pred.risk_level if pred else None)
    prediction_label  = pred.prediction_label if pred else None
    explanation       = pred.explanation       if pred else None
    recommendation    = pred.recommendation    if pred else None
    score_val         = score.score            if score else None
    classification    = (
        score.classification.value
        if score and hasattr(score.classification, "value")
        else (score.classification if score else None)
    )
    return {
        "student_id":       student_id,
        "course_id":        course_id,
        "risk_level":       risk_level,
        "prediction_label": prediction_label,
        "explanation":      explanation,
        "recommendation":   recommendation,
        "score":            score_val,
        "classification":   classification,
    }


# ── 1. Risk summary for a course ───────────────────────────────────────────────

@router.get("/risk-summary")
async def get_risk_summary(
    course_id: str,
    current_user: User = Depends(get_current_user),
):
    """Return risk level per enrolled student for a course.

    Reads only from ProgressPrediction + PerformanceScore — no recomputation.
    Teachers: own courses only.  Admins: any course.
    """
    if current_user.role == RoleEnum.STUDENT:
        raise HTTPException(status_code=403, detail="Not authorized")

    course = await CourseRepository.get_by_id(course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    if current_user.role == RoleEnum.TEACHER and course.teacher_id != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not your course")

    enrollments = await EnrollmentRepository.list_by_course(course_id)
    active = [e for e in enrollments if e.status == EnrollmentStatusEnum.ACTIVE]

    results = []
    for enr in active:
        entry = await _student_risk_entry(enr.student_id, course_id)
        student = await UserRepository.get_by_id(enr.student_id)
        entry["student_name"] = (
            (student.display_name or student.full_name()) if student else enr.student_id
        )
        results.append(entry)

    results.sort(key=lambda x: _RISK_ORDER.get(x["risk_level"], 3))

    high   = sum(1 for r in results if r["risk_level"] == "high")
    medium = sum(1 for r in results if r["risk_level"] == "medium")
    low    = sum(1 for r in results if r["risk_level"] == "low")

    return {
        "course_id":     course_id,
        "course_name":   course.name,
        "total_enrolled": len(results),
        "risk_counts":   {"high": high, "medium": medium, "low": low},
        "students":      results,
    }


# ── 2. Teacher AI assistant for a course ──────────────────────────────────────

@router.get("/teacher-assistant/{course_id}")
async def get_teacher_assistant(
    course_id: str,
    language: str = Query(default="en"),
    current_user: User = Depends(get_current_user),
):
    """AI-generated class performance summary for teachers.

    Highlights struggling students, suggests attention list.
    Derived from ProgressPrediction, PerformanceScore, AIAlert — no recomputation.
    """
    if current_user.role not in (RoleEnum.TEACHER, RoleEnum.ADMIN):
        raise HTTPException(status_code=403, detail="Not authorized")

    course = await CourseRepository.get_by_id(course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    if current_user.role == RoleEnum.TEACHER and course.teacher_id != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not your course")

    enrollments = await EnrollmentRepository.list_by_course(course_id)
    active = [e for e in enrollments if e.status == EnrollmentStatusEnum.ACTIVE]

    from app.services.ai_messages import msg as _msg
    if not active:
        return {
            "course_id":     course_id,
            "course_name":   course.name,
            "summary":       _msg("ta.no_students", language),
            "class_stats":   {},
            "attention_list": [],
            "insights":      [],
        }

    # Gather data from cached docs
    student_data = []
    for enr in active:
        score = await PerformanceScoreRepository.get(enr.student_id, course_id)
        pred  = await ProgressPredictionRepository.get(enr.student_id, course_id)
        student = await UserRepository.get_by_id(enr.student_id)
        name = (student.display_name or student.full_name()) if student else enr.student_id

        student_data.append({
            "student_id":       enr.student_id,
            "student_name":     name,
            "score":            score.score if score else None,
            "classification":   (
                score.classification.value
                if score and hasattr(score.classification, "value") else None
            ),
            "risk_level":       _safe_risk(pred.risk_level if pred else None),
            "prediction_label": pred.prediction_label if pred else None,
            "recommendation":   pred.recommendation   if pred else None,
        })

    # Aggregate stats
    scored        = [s for s in student_data if s["score"] is not None]
    avg_score     = round(sum(s["score"] for s in scored) / len(scored), 1) if scored else None
    high_risk     = [s for s in student_data if s["risk_level"] == "high"]
    medium_risk   = [s for s in student_data if s["risk_level"] == "medium"]
    needs_attn    = [s for s in student_data if s["classification"] == "needs_attention"]
    excellent     = [s for s in student_data if s["classification"] == "excellent"]
    declining     = [s for s in student_data if s["prediction_label"] in ("at_risk", "needs_intervention")]
    improving     = [s for s in student_data if s["prediction_label"] == "likely_improving"]

    # Recent alerts (last 14 days)
    cutoff = datetime.utcnow() - timedelta(days=14)
    recent_alerts = await AIAlertRepository.list_by_course(course_id, limit=20)
    recent_alerts = [a for a in recent_alerts if a.created_at >= cutoff]

    # Attention list: high risk + needs_attention
    attn_ids = {s["student_id"] for s in high_risk + needs_attn}
    attention_list = [s for s in student_data if s["student_id"] in attn_ids]

    # Readable summary
    parts = []
    if avg_score is not None:
        parts.append(_msg("ta.class_avg", language, avg=avg_score))
    if excellent:
        parts.append(_msg("ta.excellent_count", language, n=len(excellent)))
    if high_risk:
        parts.append(_msg("ta.high_risk_count", language, n=len(high_risk)))
    elif medium_risk:
        parts.append(_msg("ta.medium_risk_count", language, n=len(medium_risk)))
    if recent_alerts:
        parts.append(_msg("ta.recent_alerts", language, n=len(recent_alerts)))
    if not parts:
        parts.append(_msg("ta.all_normal", language))

    # Insight bullets
    insights = []
    if declining:
        names = ", ".join(s["student_name"] for s in declining[:3])
        suffix = "…" if len(declining) > 3 else ""
        insights.append(_msg("ta.declining_trend", language, names=names, suffix=suffix))
    if improving:
        insights.append(_msg("ta.improving_count", language, n=len(improving)))
    if needs_attn and len(active) > 0 and len(needs_attn) / len(active) > 0.3:
        insights.append(_msg("ta.group_review", language))
    for alert in recent_alerts[:3]:
        insights.append(_msg("ta.recent_alert", language, message=alert.message))

    return {
        "course_id":   course_id,
        "course_name": course.name,
        "summary":     " ".join(parts),
        "class_stats": {
            "total":         len(active),
            "avg_score":     avg_score,
            "high_risk":     len(high_risk),
            "medium_risk":   len(medium_risk),
            "low_risk":      len(active) - len(high_risk) - len(medium_risk),
            "needs_attention": len(needs_attn),
            "excellent":     len(excellent),
        },
        "attention_list": attention_list,
        "insights":      insights,
    }


# ── 3. Admin AI overview ────────────────────────────────────────────────────────

@router.get("/admin-overview")
async def get_admin_overview(
    language: str = Query(default="en"),
    current_user: User = Depends(get_current_user),
):
    """Admin AI overview: courses with highest risk, teacher load, declining trends.

    Read-only aggregation of ProgressPrediction and PerformanceScore.
    """
    if current_user.role != RoleEnum.ADMIN:
        raise HTTPException(status_code=403, detail="Admin only")

    all_predictions = await ProgressPrediction.find_all().to_list()
    all_courses     = await Course.find(Course.deleted_at == None).to_list()  # noqa: E711
    course_map      = {str(c.id): c for c in all_courses}

    # Risk counts per course
    course_risk: dict = {}
    for pred in all_predictions:
        cid = pred.course_id
        if cid not in course_risk:
            course_risk[cid] = {"high": 0, "medium": 0, "low": 0, "total": 0}
        lvl = _safe_risk(pred.risk_level)
        course_risk[cid][lvl] += 1
        course_risk[cid]["total"] += 1

    # Student risk map (student_id → latest risk)
    student_risk_map: dict = {}
    for pred in all_predictions:
        sid = pred.student_id
        # Keep most recent (list is not sorted, just overwrite — last wins)
        student_risk_map[sid] = {
            "risk_level":       _safe_risk(pred.risk_level),
            "prediction_label": pred.prediction_label,
        }

    # Top risk courses
    courses_with_risk = []
    for cid, counts in course_risk.items():
        course = course_map.get(cid)
        if not course:
            continue
        total = counts["total"]
        courses_with_risk.append({
            "course_id":      cid,
            "course_name":    course.name,
            "course_code":    course.code,
            "high_risk":      counts["high"],
            "medium_risk":    counts["medium"],
            "total_students": total,
            "risk_ratio":     round(counts["high"] / total, 2) if total > 0 else 0,
        })
    courses_with_risk.sort(key=lambda x: (x["high_risk"], x["risk_ratio"]), reverse=True)

    # Teacher workload (active/published courses)
    teacher_loads: dict = {}
    for c in all_courses:
        status_val = c.status.value if hasattr(c.status, "value") else c.status
        if status_val == "archived" or c.deleted_at is not None:
            continue
        teacher_loads[c.teacher_id] = teacher_loads.get(c.teacher_id, 0) + 1

    teacher_overload = []
    for tid, count in teacher_loads.items():
        if count >= 3:
            teacher = await UserRepository.get_by_id(tid)
            if teacher:
                teacher_overload.append({
                    "teacher_id":   tid,
                    "teacher_name": teacher.display_name or teacher.full_name(),
                    "course_count": count,
                })
    teacher_overload.sort(key=lambda x: x["course_count"], reverse=True)

    # System-wide risk counts
    risk_counts = {"high": 0, "medium": 0, "low": 0}
    for pred in all_predictions:
        lvl = _safe_risk(pred.risk_level)
        risk_counts[lvl] += 1

    # Courses with majority at_risk / needs_intervention
    declining_per_course: dict = {}
    for pred in all_predictions:
        if pred.prediction_label in ("at_risk", "needs_intervention"):
            declining_per_course[pred.course_id] = declining_per_course.get(pred.course_id, 0) + 1

    declining_courses = []
    for cid, count in declining_per_course.items():
        course = course_map.get(cid)
        total  = course_risk.get(cid, {}).get("total", 0)
        if course and total > 0 and count / total >= 0.4:
            declining_courses.append({
                "course_id":    cid,
                "course_name":  course.name,
                "at_risk_count": count,
                "total_students": total,
            })
    declining_courses.sort(key=lambda x: x["at_risk_count"], reverse=True)

    from app.services.ai_messages import msg as _msg
    # Summary text
    total_tracked = len(all_predictions)
    parts = []
    if risk_counts["high"] > 0:
        pct = round(risk_counts["high"] / total_tracked * 100) if total_tracked else 0
        parts.append(_msg("ao.high_risk", language, n=risk_counts["high"], pct=pct))
    if declining_courses:
        parts.append(_msg("ao.declining_courses", language, n=len(declining_courses)))
    if teacher_overload:
        parts.append(_msg("ao.teacher_overload", language, n=len(teacher_overload)))
    if not parts:
        parts.append(_msg("ao.stable", language))

    return {
        "summary":           " ".join(parts),
        "risk_counts":       risk_counts,
        "total_tracked":     total_tracked,
        "top_risk_courses":  courses_with_risk[:5],
        "declining_courses": declining_courses[:5],
        "teacher_overload":  teacher_overload[:5],
        "student_risk_map":  student_risk_map,
    }


# ── 4. Student insight panel ────────────────────────────────────────────────────

@router.get("/student-insights/{student_id}")
async def get_student_insights(
    student_id: str,
    language: str = Query(default="en"),
    current_user: User = Depends(get_current_user),
):
    """AI-generated readable insight bullets for a student profile.

    Aggregates LearningInsight, ProgressPrediction, FeedbackAnalysis.
    No recomputation — reads cached data only.

    RBAC: students see own; teachers/admins see any; parents see linked children.
    """
    if current_user.role == RoleEnum.STUDENT and student_id != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized")
    if current_user.role == RoleEnum.PARENT:
        if student_id not in current_user.linked_student_ids:
            raise HTTPException(status_code=403, detail="Not linked to this student")

    cutoff = datetime.utcnow() - timedelta(days=30)

    # Recent learning insights
    learning_insights = await LearningInsight.find(
        LearningInsight.student_id == student_id,
        LearningInsight.created_at >= cutoff,
    ).sort(-LearningInsight.created_at).limit(10).to_list()

    # All course predictions
    predictions = await ProgressPredictionRepository.list_by_student(student_id)

    # Recent feedback analyses
    feedback_analyses = await FeedbackAnalysis.find(
        FeedbackAnalysis.student_id == student_id,
        FeedbackAnalysis.created_at >= cutoff,
    ).sort(-FeedbackAnalysis.created_at).limit(20).to_list()

    # Performance scores
    scores = await PerformanceScoreRepository.list_by_student(student_id)

    # Classify predictions
    high_risk_preds = [p for p in predictions if p.risk_level == "high"]
    improving_preds = [p for p in predictions if p.prediction_label == "likely_improving"]
    declining_preds = [p for p in predictions if p.prediction_label in ("at_risk", "needs_intervention")]

    from app.services.ai_messages import msg as _msg
    # Build insight bullets
    insight_texts: list[str] = []

    # From learning insights (most recent, deduplicated)
    for li in learning_insights[:3]:
        insight_texts.append(li.summary)

    # From predictions
    if high_risk_preds:
        insight_texts.append(_msg("si.high_risk_courses", language, n=len(high_risk_preds)))
    elif improving_preds and not declining_preds:
        insight_texts.append(_msg("si.improving_courses", language, n=len(improving_preds)))
    elif declining_preds:
        insight_texts.append(_msg("si.declining_courses", language, n=len(declining_preds)))

    # From feedback analysis
    if feedback_analyses:
        neg = [f for f in feedback_analyses if f.sentiment_label == "negative"]
        pos = [f for f in feedback_analyses if f.sentiment_label == "positive"]
        all_tags: list[str] = []
        for f in feedback_analyses:
            all_tags.extend(f.extracted_tags)

        if neg and len(neg) > len(feedback_analyses) * 0.5:
            top_tags = list(dict.fromkeys(all_tags))[:3]
            tag_str  = ", ".join(top_tags) if top_tags else "various areas"
            insight_texts.append(_msg("si.feedback_concerns", language, tag_str=tag_str))
        elif pos and len(pos) > len(feedback_analyses) * 0.5:
            top_tags = list(dict.fromkeys(all_tags))[:3]
            if top_tags:
                insight_texts.append(_msg("si.feedback_positive", language, tag_str=", ".join(top_tags)))

    # From performance scores
    if scores:
        needs_attn = [
            s for s in scores
            if (s.classification.value if hasattr(s.classification, "value") else s.classification)
               == "needs_attention"
        ]
        avg = sum(s.score for s in scores) / len(scores)
        if needs_attn:
            insight_texts.append(_msg("si.perf_below_threshold", language, n=len(needs_attn)))
        elif avg >= 80:
            insight_texts.append(_msg("si.strong_avg", language, avg=round(avg)))

    # Deduplicate preserving order
    seen: set = set()
    unique: list[str] = []
    for text in insight_texts:
        if text not in seen:
            seen.add(text)
            unique.append(text)

    overall_trend = (
        "improving" if improving_preds and not declining_preds
        else "declining" if declining_preds
        else "stable"
    )

    return {
        "student_id":    student_id,
        "insights":      unique[:5],
        "insight_count": len(unique),
        "has_high_risk": len(high_risk_preds) > 0,
        "overall_trend": overall_trend,
    }


# ── 5. AI Feedback Suggestion ────────────────────────────────────────────────

def _build_feedback_suggestion(
    score: Optional[PerformanceScore],
    pred: Optional[ProgressPrediction],
    analyses: list,
    alerts: list,
    tone: str,
    language: str = "en",
) -> str:
    """Template-driven feedback suggestion from real student data.
    tone: 'encouraging' | 'formal' | 'constructive'
    """
    from app.services.ai_messages import msg as _msg
    parts: list[str] = []

    if score:
        val = round(score.score)
        cls = score.classification.value if hasattr(score.classification, "value") else score.classification
        att = score.attendance_score
        grd = score.grade_score

        cls_key = cls if cls in ("excellent", "good", "average", "needs_attention") else "needs_attention"
        parts.append(_msg(f"fs.score.{cls_key}.{tone}", language, val=val))

        if att < 60:
            parts.append(_msg(f"fs.att.low.{tone}", language, att=round(att)))
        elif att >= 85:
            parts.append(_msg("fs.att.high", language))

        if grd < 50 and att >= 70:
            parts.append(_msg("fs.att.grades_low", language))

    if pred:
        label = pred.prediction_label
        if label == "likely_improving":
            key = "fs.pred.improving.encouraging" if tone == "encouraging" else "fs.pred.improving.other"
            parts.append(_msg(key, language))
        elif label in ("at_risk", "needs_intervention"):
            at_risk_tone = tone if tone in ("encouraging", "formal") else "constructive"
            parts.append(_msg(f"fs.pred.at_risk.{at_risk_tone}", language))
            if pred.recommendation:
                parts.append(pred.recommendation)

    if analyses:
        neg = sum(1 for a in analyses if a.sentiment_label == "negative")
        pos = sum(1 for a in analyses if a.sentiment_label == "positive")
        all_tags: list[str] = []
        for a in analyses:
            all_tags.extend(a.extracted_tags or [])
        top_tags = list(dict.fromkeys(all_tags))[:3]
        if neg >= 2 and top_tags:
            area_str = " and ".join(top_tags[:2])
            if tone == "encouraging":
                parts.append(_msg("fs.fb.neg.encouraging", language, area_str=area_str))
            else:
                parts.append(_msg("fs.fb.neg.other", language, areas=", ".join(top_tags)))
        elif pos >= 2 and top_tags:
            parts.append(_msg("fs.fb.pos", language, areas=", ".join(top_tags[:2])))

    if alerts:
        msg_lower = alerts[0].message.lower()
        if "attendance" in msg_lower and tone == "encouraging":
            parts.append(_msg("fs.alert.attendance.encouraging", language))
        elif ("negative" in msg_lower or "feedback" in msg_lower) and tone == "encouraging":
            parts.append(_msg("fs.alert.feedback.encouraging", language))

    parts.append(_msg(f"fs.closing.{tone}", language))

    if not parts or len(parts) == 1:
        return _msg(f"fs.empty.{tone}", language)

    return " ".join(parts)


@router.post("/suggest-feedback")
async def suggest_feedback(
    body: dict,
    current_user: User = Depends(get_current_user),
):
    """Generate a template-driven feedback suggestion from existing student data.

    Reads: PerformanceScore, ProgressPrediction, FeedbackAnalysis, AIAlert (all cached).
    Does NOT modify any academic records.
    Does NOT auto-submit feedback — teacher reviews and edits before sending.

    Teacher: own courses only.  Admin: any course.
    """
    if current_user.role not in (RoleEnum.TEACHER, RoleEnum.ADMIN):
        raise HTTPException(status_code=403, detail="Not authorized")

    student_id: str = body.get("student_id", "")
    course_id: str  = body.get("course_id", "")
    tone: str       = body.get("tone", "constructive")
    language: str   = body.get("language", "en")

    if not student_id or not course_id:
        raise HTTPException(status_code=422, detail="student_id and course_id are required")
    if tone not in ("encouraging", "formal", "constructive"):
        tone = "constructive"

    if current_user.role == RoleEnum.TEACHER:
        course = await CourseRepository.get_by_id(course_id)
        if not course or course.teacher_id != str(current_user.id):
            raise HTTPException(status_code=403, detail="Not your course")

    cutoff   = datetime.utcnow() - timedelta(days=45)
    score    = await PerformanceScoreRepository.get(student_id, course_id)
    pred     = await ProgressPredictionRepository.get(student_id, course_id)
    analyses = await FeedbackAnalysis.find(
        FeedbackAnalysis.student_id == student_id,
        FeedbackAnalysis.course_id  == course_id,
        FeedbackAnalysis.created_at >= cutoff,
    ).sort(-FeedbackAnalysis.created_at).limit(5).to_list()
    alerts = await AIAlert.find(
        AIAlert.student_id == student_id,
        AIAlert.course_id  == course_id,
    ).sort(-AIAlert.created_at).limit(3).to_list()

    data_used: list[str] = []
    if score:     data_used.append("performance_score")
    if pred:      data_used.append("progress_prediction")
    if analyses:  data_used.append("feedback_history")
    if alerts:    data_used.append("ai_alerts")

    suggestion = _build_feedback_suggestion(score, pred, analyses, alerts, tone, language)

    return {
        "suggested_text": suggestion,
        "tone":           tone,
        "data_used":      data_used,
        "has_data":       len(data_used) > 0,
    }


# ── 6. Role-aware dashboard insights ────────────────────────────────────────────

async def _teacher_insights(user: User, language: str = "en") -> list:
    published = await Course.find(
        Course.teacher_id == str(user.id),
        Course.deleted_at == None,
        Course.status     == CourseStatusEnum.PUBLISHED,
    ).to_list()

    from app.services.ai_messages import msg as _msg
    if not published:
        return [_msg("di.teacher.no_courses", language)]

    bullets: list[str] = []
    total_high_risk = 0
    total_needs_att = 0
    total_improving = 0
    best_course: str | None  = None
    best_avg:    float | None = None

    for course in published:
        cid = str(course.id)
        enrollments = await EnrollmentRepository.list_by_course(cid)
        active = [e for e in enrollments if e.status == EnrollmentStatusEnum.ACTIVE]
        if not active:
            continue

        scored: list[float] = []
        for enr in active:
            score = await PerformanceScoreRepository.get(enr.student_id, cid)
            pred  = await ProgressPredictionRepository.get(enr.student_id, cid)
            if score:
                scored.append(score.score)
                cls = score.classification.value if hasattr(score.classification, "value") else score.classification
                if cls == "needs_attention":
                    total_needs_att += 1
            if pred:
                if pred.risk_level == "high":
                    total_high_risk += 1
                if pred.prediction_label == "likely_improving":
                    total_improving += 1

        if scored:
            avg = sum(scored) / len(scored)
            if best_avg is None or avg > best_avg:
                best_avg = avg
                best_course = course.name

    if total_high_risk > 0:
        bullets.append(_msg("di.teacher.high_risk", language, n=total_high_risk))
    elif total_needs_att > 0:
        bullets.append(_msg("di.teacher.needs_attn", language, n=total_needs_att))

    if total_improving > 0:
        bullets.append(_msg("di.teacher.improving", language, n=total_improving))

    if best_course and best_avg is not None:
        bullets.append(_msg("di.teacher.best_course", language, course=best_course, avg=round(best_avg)))

    cutoff = datetime.utcnow() - timedelta(days=14)
    recent_fas: list = []
    for course in published[:3]:
        batch = await FeedbackAnalysis.find(
            FeedbackAnalysis.course_id  == str(course.id),
            FeedbackAnalysis.created_at >= cutoff,
        ).limit(10).to_list()
        recent_fas.extend(batch)

    if recent_fas:
        total_fa = len(recent_fas)
        pos = sum(1 for a in recent_fas if a.sentiment_label == "positive")
        neg = sum(1 for a in recent_fas if a.sentiment_label == "negative")
        if pos / total_fa > 0.6:
            bullets.append(_msg("di.teacher.pos_feedback", language))
        elif neg / total_fa > 0.5:
            bullets.append(_msg("di.teacher.neg_feedback", language))

    if not bullets:
        bullets.append(_msg("di.teacher.all_normal", language))

    return bullets[:4]


async def _student_insights(user: User, language: str = "en") -> list:
    student_id  = str(user.id)
    cutoff      = datetime.utcnow() - timedelta(days=30)
    predictions = await ProgressPredictionRepository.list_by_student(student_id)
    scores      = await PerformanceScoreRepository.list_by_student(student_id)
    li_recent   = await LearningInsight.find(
        LearningInsight.student_id == student_id,
        LearningInsight.created_at >= cutoff,
    ).sort(-LearningInsight.created_at).limit(5).to_list()

    from app.services.ai_messages import msg as _msg
    bullets: list[str] = []

    if scores:
        avg = sum(s.score for s in scores) / len(scores)
        if avg >= 80:
            bullets.append(_msg("di.student.avg_excellent", language, avg=round(avg)))
        elif avg >= 60:
            bullets.append(_msg("di.student.avg_solid", language, avg=round(avg)))
        else:
            bullets.append(_msg("di.student.avg_low", language, avg=round(avg)))

    high_risk = [p for p in predictions if p.risk_level == "high"]
    improving  = [p for p in predictions if p.prediction_label == "likely_improving"]
    declining  = [p for p in predictions if p.prediction_label in ("at_risk", "needs_intervention")]

    if high_risk:
        bullets.append(_msg("di.student.high_risk", language, n=len(high_risk)))
    elif improving and not declining:
        bullets.append(_msg("di.student.improving", language, n=len(improving)))
    elif declining:
        bullets.append(_msg("di.student.declining", language, n=len(declining)))

    if li_recent and len(bullets) < 3:
        bullets.append(li_recent[0].summary)

    if not bullets:
        bullets.append(_msg("di.student.no_data", language))

    return bullets[:4]


async def _parent_insights(user: User, language: str = "en") -> list:
    from app.services.ai_messages import msg as _msg
    linked_ids = user.linked_student_ids or []
    if not linked_ids:
        return [_msg("di.parent.no_children", language)]

    bullets: list[str] = []
    cutoff = datetime.utcnow() - timedelta(days=14)

    for student_id in linked_ids:
        student = await UserRepository.get_by_id(student_id)
        child_name = student.full_name() if student else "your child"

        predictions = await ProgressPredictionRepository.list_by_student(student_id)
        high_risk   = [p for p in predictions if p.risk_level == "high"]
        improving   = [p for p in predictions if p.prediction_label == "likely_improving"]

        if high_risk:
            bullets.append(_msg("di.parent.child_high_risk", language, child=child_name, n=len(high_risk)))
        elif improving:
            bullets.append(_msg("di.parent.child_improving", language, child=child_name, n=len(improving)))

        recent_alerts = await AIAlert.find(
            AIAlert.student_id == student_id,
            AIAlert.created_at >= cutoff,
        ).sort(-AIAlert.created_at).limit(1).to_list()

        if recent_alerts:
            alert_text = recent_alerts[0].message
            if len(alert_text) > 80:
                alert_text = alert_text[:77] + "…"
            bullets.append(_msg("di.parent.child_alert", language, child=child_name, message=alert_text))

        li = await LearningInsight.find(
            LearningInsight.student_id == student_id,
            LearningInsight.created_at >= cutoff,
        ).sort(-LearningInsight.created_at).limit(1).to_list()
        if li and len(bullets) < 4:
            bullets.append(li[0].summary)

        if len(bullets) >= 4:
            break

    if not bullets:
        bullets.append(_msg("di.parent.all_stable", language))

    return bullets[:4]


async def _admin_insights(user: User, language: str = "en") -> list:
    all_preds     = await ProgressPrediction.find_all().to_list()
    cutoff        = datetime.utcnow() - timedelta(days=7)
    recent_alerts = await AIAlert.find(AIAlert.created_at >= cutoff).to_list()
    published     = await Course.find(
        Course.deleted_at == None,
        Course.status     == CourseStatusEnum.PUBLISHED,
    ).to_list()

    from app.services.ai_messages import msg as _msg
    bullets: list[str] = []

    high_risk = [p for p in all_preds if p.risk_level == "high"]
    if high_risk:
        unique_s = len({p.student_id for p in high_risk})
        bullets.append(_msg("di.admin.high_risk", language, n=unique_s))

    if recent_alerts:
        bullets.append(_msg("di.admin.alerts", language, n=len(recent_alerts)))

    if published:
        bullets.append(_msg("di.admin.active_courses", language, n=len(published)))

    at_risk  = [p for p in all_preds if p.prediction_label in ("at_risk", "needs_intervention")]
    improving = [p for p in all_preds if p.prediction_label == "likely_improving"]
    if at_risk:
        bullets.append(_msg("di.admin.at_risk_enroll", language, n=len(at_risk)))
    elif improving:
        bullets.append(_msg("di.admin.improving_enroll", language, n=len(improving)))

    if not bullets:
        bullets.append(_msg("di.admin.stable", language))

    return bullets[:4]


@router.get("/dashboard-insights")
async def get_dashboard_insights(
    language: str = Query(default="en"),
    current_user: User = Depends(get_current_user),
):
    """Role-aware AI insight bullets for the dashboard overview.

    Reads only pre-computed/cached documents — no recomputation at query time.
    Returns up to 4 bullet-point insights tailored to the user's role.

    Teacher: student risk, trends, best course, feedback sentiment.
    Student: personal average, risk level, improvement trends.
    Parent:  per-child risk, alerts, learning insights.
    Admin:   platform-wide risk counts, recent alerts, active courses.
    """
    if current_user.role == RoleEnum.TEACHER:
        bullets = await _teacher_insights(current_user, language)
    elif current_user.role == RoleEnum.STUDENT:
        bullets = await _student_insights(current_user, language)
    elif current_user.role == RoleEnum.PARENT:
        bullets = await _parent_insights(current_user, language)
    elif current_user.role == RoleEnum.ADMIN:
        bullets = await _admin_insights(current_user, language)
    else:
        bullets = []

    return {"insights": bullets, "count": len(bullets)}
