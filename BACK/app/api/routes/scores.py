"""Performance Score routes.

GET  /api/scores/{student_id}/{course_id}          — latest score for an enrollment
GET  /api/scores/{student_id}                      — all scores for a student
GET  /api/scores/{student_id}/{course_id}/history  — score history (time-series)
POST /api/scores/{student_id}/{course_id}/compute  — force recompute (teacher/admin)
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from app.models import User, RoleEnum, PerformanceScore, ScoreHistory
from app.schemas import PerformanceScoreResponse
from app.security import get_current_user
from app.repositories import PerformanceScoreRepository, EnrollmentRepository

router = APIRouter(prefix="/api/scores", tags=["scores"])


def _serialize_score(ps: PerformanceScore) -> dict:
    return {
        "id": str(ps.id),
        "student_id": ps.student_id,
        "course_id": ps.course_id,
        "score": ps.score,
        "classification": ps.classification.value if hasattr(ps.classification, "value") else ps.classification,
        "grade_score": ps.grade_score,
        "attendance_score": ps.attendance_score,
        "feedback_score": ps.feedback_score,
        "trend_score": ps.trend_score,
        "computed_at": ps.computed_at,
    }


def _serialize_history(sh: ScoreHistory) -> dict:
    return {
        "id": str(sh.id),
        "student_id": sh.student_id,
        "course_id": sh.course_id,
        "score": sh.score,
        "classification": sh.classification.value if hasattr(sh.classification, "value") else sh.classification,
        "computed_at": sh.computed_at,
    }


def _can_view(current_user: User, student_id: str) -> bool:
    """Admin always allowed. Teacher access is checked separately via _teacher_can_view.
    Student and parent checks are identity/link based."""
    if current_user.role == RoleEnum.ADMIN:
        return True
    if current_user.role == RoleEnum.STUDENT:
        return str(current_user.id) == student_id
    if current_user.role == RoleEnum.PARENT:
        return student_id in current_user.linked_student_ids
    return False


async def _teacher_can_view(teacher: User, student_id: str, course_id: str) -> bool:
    """Teacher may view a score only if the student is enrolled in one of their courses."""
    from app.repositories import CourseRepository as CR
    course = await CR.get_by_id(course_id)
    return bool(course and course.teacher_id == str(teacher.id))


@router.get("/{student_id}/{course_id}", response_model=PerformanceScoreResponse)
async def get_score(
    student_id: str,
    course_id: str,
    current_user: User = Depends(get_current_user),
):
    if current_user.role == RoleEnum.TEACHER:
        if not await _teacher_can_view(current_user, student_id, course_id):
            raise HTTPException(status_code=403, detail="Not authorized")
    elif not _can_view(current_user, student_id):
        raise HTTPException(status_code=403, detail="Not authorized")
    ps = await PerformanceScoreRepository.get(student_id, course_id)
    if not ps:
        raise HTTPException(status_code=404, detail="Score not computed yet")
    return PerformanceScoreResponse(**_serialize_score(ps))


@router.get("/{student_id}", response_model=List[PerformanceScoreResponse])
async def get_all_scores(
    student_id: str,
    current_user: User = Depends(get_current_user),
):
    if not _can_view(current_user, student_id):
        raise HTTPException(status_code=403, detail="Not authorized")
    scores = await PerformanceScoreRepository.list_by_student(student_id)
    return [PerformanceScoreResponse(**_serialize_score(ps)) for ps in scores]


@router.get("/{student_id}/{course_id}/history")
async def get_score_history(
    student_id: str,
    course_id: str,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
):
    if current_user.role == RoleEnum.TEACHER:
        if not await _teacher_can_view(current_user, student_id, course_id):
            raise HTTPException(status_code=403, detail="Not authorized")
    elif not _can_view(current_user, student_id):
        raise HTTPException(status_code=403, detail="Not authorized")
    history = await PerformanceScoreRepository.get_history(student_id, course_id, limit=limit)
    return [_serialize_history(sh) for sh in history]


@router.get("/{student_id}/{course_id}/prediction")
async def get_prediction(
    student_id: str,
    course_id: str,
    current_user: User = Depends(get_current_user),
):
    """Return the current academic prediction for this enrollment.

    All roles receive the human-readable explanation and recommendation.
    Students / parents do not receive the internal risk_level label.
    """
    if current_user.role == RoleEnum.TEACHER:
        if not await _teacher_can_view(current_user, student_id, course_id):
            raise HTTPException(status_code=403, detail="Not authorized")
    elif not _can_view(current_user, student_id):
        raise HTTPException(status_code=403, detail="Not authorized")

    from app.repositories import ProgressPredictionRepository
    pred = await ProgressPredictionRepository.get(student_id, course_id)
    if not pred:
        return {"prediction_label": None, "explanation": None, "recommendation": None}

    base: dict = {
        "prediction_label": pred.prediction_label,
        "explanation":      pred.explanation,
        "recommendation":   pred.recommendation,
        "computed_at":      pred.computed_at,
    }
    if current_user.role in (RoleEnum.TEACHER, RoleEnum.ADMIN):
        base["risk_level"] = pred.risk_level
    return base


@router.get("/{student_id}/predictions")
async def get_all_predictions(
    student_id: str,
    current_user: User = Depends(get_current_user),
):
    """All course predictions for a student — used by ProgressPage."""
    if not _can_view(current_user, student_id):
        raise HTTPException(status_code=403, detail="Not authorized")

    from app.repositories import ProgressPredictionRepository
    preds = await ProgressPredictionRepository.list_by_student(student_id)
    return [
        {
            "course_id":        p.course_id,
            "prediction_label": p.prediction_label,
            "explanation":      p.explanation,
            "recommendation":   p.recommendation,
            "risk_level":       p.risk_level if current_user.role in (RoleEnum.TEACHER, RoleEnum.ADMIN) else None,
            "computed_at":      p.computed_at,
        }
        for p in preds
    ]


@router.get("/{student_id}/{course_id}/feedback-insight")
async def get_feedback_insight(
    student_id: str,
    course_id: str,
    current_user: User = Depends(get_current_user),
):
    """Human-readable feedback analysis summary for this enrollment.

    Teachers / admins: full tag list, contribution score, and recent entries.
    Students / parents: plain-language summary sentence only.
    """
    if not _can_view(current_user, student_id):
        raise HTTPException(status_code=403, detail="Not authorized")

    from app.repositories import FeedbackAnalysisRepository
    from app.services.feedback_analysis_service import FeedbackAnalysisService

    analyses = await FeedbackAnalysisRepository.list_by_student_course(student_id, course_id)
    if not analyses:
        return {"summary": None, "tags": [], "contribution": None, "count": 0}

    recent = analyses[:5]

    tag_counts: dict = {}
    for a in recent:
        for t in a.extracted_tags:
            tag_counts[t] = tag_counts.get(t, 0) + 1
    top_tags = [t for t, _ in sorted(tag_counts.items(), key=lambda x: -x[1])[:3]]

    avg_contribution = round(sum(a.calculated_contribution for a in recent) / len(recent), 1)
    dominant_sentiment = recent[0].sentiment_label
    summary = FeedbackAnalysisService.build_human_summary(analyses)

    base: dict = {
        "summary":            summary,
        "dominant_sentiment": dominant_sentiment,
        "count":              len(analyses),
    }

    if current_user.role in (RoleEnum.TEACHER, RoleEnum.ADMIN):
        base["tags"]         = top_tags
        base["contribution"] = avg_contribution
        base["recent"] = [
            {
                "feedback_id":             a.feedback_id,
                "sentiment_label":         a.sentiment_label,
                "sentiment_score":         a.sentiment_score,
                "extracted_tags":          a.extracted_tags,
                "confidence":              a.confidence,
                "calculated_contribution": a.calculated_contribution,
                "created_at":              a.created_at,
            }
            for a in recent
        ]
    else:
        base["tags"]         = []
        base["contribution"] = None

    return base


@router.post("/{student_id}/{course_id}/compute", response_model=PerformanceScoreResponse)
async def force_compute_score(
    student_id: str,
    course_id: str,
    current_user: User = Depends(get_current_user),
):
    """Force recompute the score.  Teachers (own course) / admins only."""
    if current_user.role == RoleEnum.ADMIN:
        pass
    elif current_user.role == RoleEnum.TEACHER:
        if not await _teacher_can_view(current_user, student_id, course_id):
            raise HTTPException(status_code=403, detail="Not your course")
    else:
        raise HTTPException(status_code=403, detail="Teachers and admins only")
    from app.services.score_service import compute_and_save
    ps = await compute_and_save(student_id, course_id)
    if not ps:
        raise HTTPException(status_code=500, detail="Score computation failed")
    return PerformanceScoreResponse(**_serialize_score(ps))
