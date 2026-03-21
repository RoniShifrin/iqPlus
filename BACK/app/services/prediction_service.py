"""Rule-based Academic Progress Prediction Service.

Computes a forward-looking label and explanation for a student's academic
trajectory in a course.  All rules are explicit and every output includes a
human-readable explanation — no opaque model outputs.

Prediction labels
-----------------
  likely_improving    — strong upward trend, high score
  likely_stable       — steady performance, no major concerns
  at_risk             — declining trend or low score, needs attention soon
  needs_intervention  — critically low score or severe attendance problems

Risk levels
-----------
  low    — no immediate concern
  medium — monitor closely
  high   — teacher / parent action recommended

Inputs used
-----------
  PerformanceScore  — composite score + component breakdowns
  ScoreHistory      — last 5 entries to determine trajectory
  ProgressMetrics   — trend_direction, attendance_rate
  LearningInsight   — recent decline/improvement events
"""
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# ── Thresholds ───────────────────────────────────────────────────────────────
EXCELLENT_THRESHOLD    = 80.0
GOOD_THRESHOLD         = 65.0
AVERAGE_THRESHOLD      = 50.0
LOW_ATTENDANCE_WARN    = 75.0   # attendance below this is a concern
LOW_ATTENDANCE_CRIT    = 60.0   # attendance below this is critical
SCORE_TREND_DELTA      = 4.0    # score change to call a trend meaningful


def _score_trend(history: list) -> str:
    """Return 'improving', 'declining', or 'stable' from a list of ScoreHistory docs."""
    if len(history) < 2:
        return "stable"
    newest = history[0].score
    oldest = history[-1].score
    delta = newest - oldest
    if delta > SCORE_TREND_DELTA:
        return "improving"
    if delta < -SCORE_TREND_DELTA:
        return "declining"
    return "stable"


def _has_recent_decline(insights: list) -> bool:
    from app.models import InsightTypeEnum
    return any(
        getattr(i, "insight_type", None) in (
            InsightTypeEnum.PERFORMANCE_DECLINE,
            InsightTypeEnum.ATTENDANCE_CONCERN,
        )
        for i in insights
    )


def _has_recent_improvement(insights: list) -> bool:
    from app.models import InsightTypeEnum
    return any(
        getattr(i, "insight_type", None) in (
            InsightTypeEnum.PERFORMANCE_IMPROVEMENT,
            InsightTypeEnum.ATTENDANCE_IMPROVEMENT,
        )
        for i in insights
    )


# ── Core prediction logic ─────────────────────────────────────────────────────

def _compute_prediction(
    score: float,
    attendance: float,
    metrics_trend: str,
    history_trend: str,
    has_decline_insight: bool,
    has_improvement_insight: bool,
    feedback_score: float,
) -> dict:
    reasons: list[str] = []
    rec: str = ""

    # --- Attendance signals ---
    if attendance < LOW_ATTENDANCE_CRIT:
        reasons.append(f"attendance is critically low ({attendance:.0f}%)")
    elif attendance < LOW_ATTENDANCE_WARN:
        reasons.append(f"attendance is below the recommended level ({attendance:.0f}%)")

    # --- Score level signals ---
    if score >= EXCELLENT_THRESHOLD:
        reasons.append(f"current score is excellent ({score:.0f}/100)")
    elif score >= GOOD_THRESHOLD:
        reasons.append(f"current score is good ({score:.0f}/100)")
    elif score >= AVERAGE_THRESHOLD:
        reasons.append(f"current score is average ({score:.0f}/100)")
    else:
        reasons.append(f"current score is below average ({score:.0f}/100)")

    # --- Trend signals ---
    effective_trend = history_trend if history_trend != "stable" else metrics_trend
    if effective_trend == "improving":
        reasons.append("performance trend is improving")
    elif effective_trend == "declining":
        reasons.append("performance trend is declining")

    # --- Feedback signals ---
    if feedback_score < 40:
        reasons.append("recent teacher feedback indicates concerns")
    elif feedback_score > 70:
        reasons.append("recent teacher feedback is positive")

    # --- Insight events ---
    if has_decline_insight:
        reasons.append("a recent decline alert was triggered")
    elif has_improvement_insight:
        reasons.append("a recent improvement was noted")

    # ── Determine label + risk ────────────────────────────────────────────────

    # Critical: needs intervention
    if score < AVERAGE_THRESHOLD and attendance < LOW_ATTENDANCE_CRIT:
        label = "needs_intervention"
        risk  = "high"
        explanation = (
            "This student needs immediate support. "
            + " ".join(f"The {r}." for r in reasons[:3])
        )
        rec = (
            "Schedule a meeting with the student and parent. "
            "Consider additional tutoring or a support plan."
        )

    elif score < AVERAGE_THRESHOLD or (
        score < GOOD_THRESHOLD and effective_trend == "declining"
    ):
        label = "at_risk"
        risk  = "high" if score < AVERAGE_THRESHOLD else "medium"
        explanation = (
            "This student is at risk of falling behind. "
            + " ".join(f"The {r}." for r in reasons[:3])
        )
        rec = (
            "Provide additional feedback and check in with the student. "
            "Notify the parent if progress does not improve."
        )

    elif score >= EXCELLENT_THRESHOLD and effective_trend in ("improving", "stable"):
        label = "likely_improving"
        risk  = "low"
        explanation = (
            "This student is on a strong academic path. "
            + " ".join(f"The {r}." for r in reasons[:3])
        )
        rec = "Maintain current engagement. Offer advanced opportunities if appropriate."

    elif has_decline_insight and effective_trend == "declining":
        label = "at_risk"
        risk  = "medium"
        explanation = (
            "Recent indicators suggest a downward trend. "
            + " ".join(f"The {r}." for r in reasons[:3])
        )
        rec = "Monitor closely over the next two weeks. Provide targeted feedback."

    else:
        label = "likely_stable"
        risk  = "low" if score >= GOOD_THRESHOLD else "medium"
        explanation = (
            "Performance is broadly stable with no major concerns. "
            + " ".join(f"The {r}." for r in reasons[:3])
        )
        if score >= GOOD_THRESHOLD:
            rec = "Encourage continued effort to reach the excellent category."
        else:
            rec = "Focus on consistency in attendance and assignment completion."

    return {
        "prediction_label": label,
        "explanation":      explanation,
        "recommendation":   rec,
        "risk_level":       risk,
    }


# ── Service class ─────────────────────────────────────────────────────────────

class PredictionService:
    """Entry points called from score_service after compute_and_save."""

    @staticmethod
    async def predict_and_save(
        student_id: str,
        course_id: str,
        ps,                  # PerformanceScore document (already computed)
    ) -> Optional[object]:
        """Compute and upsert a ProgressPrediction for this enrollment."""
        try:
            from app.models import ProgressPrediction
            from app.repositories import ProgressPredictionRepository, ProgressMetricsRepository
            from app.repositories import LearningInsightRepository, PerformanceScoreRepository

            # Score history (most recent 5)
            history = await PerformanceScoreRepository.get_history(student_id, course_id, limit=5)

            # Progress metrics (attendance + trend)
            metrics = await ProgressMetricsRepository.get(student_id, course_id)
            attendance = metrics.attendance_rate if metrics else 0.0
            metrics_trend = metrics.trend_direction if metrics else "stable"

            # Recent learning insights (last 5)
            insights = await LearningInsightRepository.list_by_student(student_id, limit=5)
            course_insights = [i for i in insights if i.course_id == course_id]

            history_trend = _score_trend(history)

            result = _compute_prediction(
                score=ps.score,
                attendance=attendance,
                metrics_trend=metrics_trend,
                history_trend=history_trend,
                has_decline_insight=_has_recent_decline(course_insights),
                has_improvement_insight=_has_recent_improvement(course_insights),
                feedback_score=ps.feedback_score,
            )

            pred = await ProgressPredictionRepository.upsert(
                student_id=student_id,
                course_id=course_id,
                **result,
            )
            logger.info(
                "Prediction student=%s course=%s → %s (%s)",
                student_id, course_id, result["prediction_label"], result["risk_level"],
            )
            return pred

        except Exception as exc:
            logger.error("PredictionService.predict_and_save failed: %s", exc)
            return None
