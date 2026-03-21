"""Usability Feedback routes.

POST /api/usability/feedback     — any authenticated user submits a rating
GET  /api/usability/feedback     — admin views all submissions with averages
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from app.models import User, RoleEnum, UsabilityFeedback
from app.schemas import UsabilityFeedbackCreate, UsabilityFeedbackResponse
from app.security import get_current_user

router = APIRouter(prefix="/api/usability", tags=["usability"])


def _serialize(f: UsabilityFeedback) -> dict:
    return {
        "id": str(f.id),
        "user_id": f.user_id,
        "report_clarity": f.report_clarity,
        "dashboard_usability": f.dashboard_usability,
        "navigation_ease": f.navigation_ease,
        "comment": f.comment,
        "created_at": f.created_at,
    }


@router.post("/feedback", response_model=UsabilityFeedbackResponse, status_code=status.HTTP_201_CREATED)
async def submit_usability_feedback(
    body: UsabilityFeedbackCreate,
    current_user: User = Depends(get_current_user),
):
    fb = UsabilityFeedback(
        user_id=str(current_user.id),
        report_clarity=body.report_clarity,
        dashboard_usability=body.dashboard_usability,
        navigation_ease=body.navigation_ease,
        comment=body.comment,
    )
    await fb.insert()
    return UsabilityFeedbackResponse(**_serialize(fb))


@router.get("/feedback", response_model=List[UsabilityFeedbackResponse])
async def list_usability_feedback(
    limit: int = 100,
    current_user: User = Depends(get_current_user),
):
    """Admin-only: list all submissions."""
    if current_user.role != RoleEnum.ADMIN:
        raise HTTPException(status_code=403, detail="Admin only")
    entries = await UsabilityFeedback.find_all().sort(-UsabilityFeedback.created_at).limit(limit).to_list()
    return [UsabilityFeedbackResponse(**_serialize(f)) for f in entries]


@router.get("/feedback/summary")
async def usability_summary(current_user: User = Depends(get_current_user)):
    """Admin-only: return average ratings across all submissions."""
    if current_user.role != RoleEnum.ADMIN:
        raise HTTPException(status_code=403, detail="Admin only")
    entries = await UsabilityFeedback.find_all().to_list()
    if not entries:
        return {"count": 0, "avg_report_clarity": None, "avg_dashboard_usability": None, "avg_navigation_ease": None}
    n = len(entries)
    return {
        "count": n,
        "avg_report_clarity":     round(sum(e.report_clarity for e in entries) / n, 2),
        "avg_dashboard_usability": round(sum(e.dashboard_usability for e in entries) / n, 2),
        "avg_navigation_ease":    round(sum(e.navigation_ease for e in entries) / n, 2),
    }
