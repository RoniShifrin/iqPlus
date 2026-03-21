"""Student Performance Score Engine.

Computes a composite 0-100 score per (student, course) enrollment:
  - Grades       50%  — average grade normalised to 0-100
  - Attendance   20%  — attendance rate (0-100)
  - Feedback     20%  — text-analysed contribution (FeedbackAnalysis.calculated_contribution)
                        falls back to enum-based score when no analysis exists
  - Trend        10%  — improving=100, stable=50, declining=0

Classification:
  >= 80  → excellent
  >= 65  → good
  >= 50  → average
  <  50  → needs_attention
"""
import logging
from datetime import datetime

from app.models import (
    PerformanceScore, ScoreHistory,
    ScoreClassificationEnum, SentimentEnum,
)
from app.repositories import (
    LessonRecordRepository, ProgressMetricsRepository, FeedbackRepository,
    FeedbackAnalysisRepository,
)

logger = logging.getLogger(__name__)

# Weights (must sum to 1.0)
W_GRADES     = 0.50
W_ATTENDANCE = 0.20
W_FEEDBACK   = 0.20
W_TREND      = 0.10

_TREND_SCORES = {"improving": 100.0, "stable": 50.0, "declining": 0.0}


def _classify(score: float) -> ScoreClassificationEnum:
    if score >= 80:
        return ScoreClassificationEnum.EXCELLENT
    if score >= 65:
        return ScoreClassificationEnum.GOOD
    if score >= 50:
        return ScoreClassificationEnum.AVERAGE
    return ScoreClassificationEnum.NEEDS_ATTENTION


async def compute_and_save(student_id: str, course_id: str) -> PerformanceScore | None:
    """Compute the performance score and persist it.  Returns the saved document."""
    try:
        # Grades component
        records = await LessonRecordRepository.get_by_student_course(
            student_id, course_id, limit=50
        )
        grades = [r.grade_value for r in records if r.grade_value is not None]
        grade_raw = (sum(grades) / len(grades)) if grades else 0.0

        # Attendance component — from progress metrics (already computed)
        metrics = await ProgressMetricsRepository.get(student_id, course_id)
        attendance_raw = metrics.attendance_rate if metrics else 0.0
        trend_raw = _TREND_SCORES.get(
            metrics.trend_direction if metrics else "stable", 50.0
        )

        # Feedback component — prefer text-analysis contributions when available.
        # FeedbackAnalysis.calculated_contribution is produced by
        # feedback_analysis_service.py and blends enum signal with keyword NLP.
        # Falls back to enum-only scoring for enrollments that pre-date the
        # analysis service or where no text analysis has been run yet.
        analyses = await FeedbackAnalysisRepository.list_by_student_course(
            student_id, course_id
        )
        if analyses:
            # Use the most recent 10 analysis results (weighted equally for now)
            recent = analyses[:10]
            feedback_raw = sum(a.calculated_contribution for a in recent) / len(recent)
        else:
            # Legacy fallback: enum-based average
            feedbacks = await FeedbackRepository.list_by_student_course(student_id, course_id)
            if feedbacks:
                sentiment_map = {
                    SentimentEnum.POSITIVE: 100.0,
                    SentimentEnum.NEUTRAL:  50.0,
                    SentimentEnum.NEGATIVE:  0.0,
                }
                feedback_raw = sum(
                    sentiment_map.get(f.sentiment, 50.0) for f in feedbacks
                ) / len(feedbacks)
            else:
                feedback_raw = 50.0  # neutral default when no feedback exists

        # Composite score
        score = (
            grade_raw     * W_GRADES
            + attendance_raw * W_ATTENDANCE
            + feedback_raw   * W_FEEDBACK
            + trend_raw      * W_TREND
        )
        score = round(min(max(score, 0.0), 100.0), 2)
        classification = _classify(score)

        # Upsert PerformanceScore (one doc per enrollment)
        existing = await PerformanceScore.find_one(
            PerformanceScore.student_id == student_id,
            PerformanceScore.course_id == course_id,
        )
        now = datetime.utcnow()
        if existing:
            await existing.set({
                PerformanceScore.score: score,
                PerformanceScore.classification: classification,
                PerformanceScore.grade_score: grade_raw,
                PerformanceScore.attendance_score: attendance_raw,
                PerformanceScore.feedback_score: feedback_raw,
                PerformanceScore.trend_score: trend_raw,
                PerformanceScore.computed_at: now,
            })
            ps = existing
        else:
            ps = PerformanceScore(
                student_id=student_id,
                course_id=course_id,
                score=score,
                classification=classification,
                grade_score=grade_raw,
                attendance_score=attendance_raw,
                feedback_score=feedback_raw,
                trend_score=trend_raw,
            )
            await ps.insert()

        # Append to history (always a new entry)
        await ScoreHistory(
            student_id=student_id,
            course_id=course_id,
            score=score,
            classification=classification,
        ).insert()

        logger.info(
            "Score computed student=%s course=%s → %.1f (%s)",
            student_id, course_id, score, classification.value,
        )

        # Compute / update prediction in the background (never blocks score return)
        try:
            from app.services.prediction_service import PredictionService
            await PredictionService.predict_and_save(student_id, course_id, ps)
        except Exception as pred_exc:
            logger.warning("Prediction update skipped: %s", pred_exc)

        return ps

    except Exception as exc:
        logger.error("score_service.compute_and_save failed: %s", exc)
        return None
