"""Notification API routes"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

from app.models import User
from app.schemas import NotificationResponse
from app.security import get_current_user
from app.repositories import NotificationRepository

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


def _serialize(n) -> dict:
    return {
        "id": str(n.id),
        "user_id": n.user_id,
        "message": n.message,
        "type": n.type,
        "title": getattr(n, "title", None),
        "course_id": getattr(n, "course_id", None),
        "related_entity_type": getattr(n, "related_entity_type", None),
        "related_entity_id": getattr(n, "related_entity_id", None),
        "read_status": n.read_status,
        "created_at": n.created_at,
    }


@router.get("/", response_model=List[NotificationResponse])
async def list_notifications(
    limit: int = 20,
    current_user: User = Depends(get_current_user),
):
    notifs = await NotificationRepository.list_by_user(str(current_user.id), limit=limit)
    return [NotificationResponse(**_serialize(n)) for n in notifs]


@router.get("/unread-count")
async def unread_count(current_user: User = Depends(get_current_user)):
    count = await NotificationRepository.unread_count(str(current_user.id))
    return {"count": count}


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
async def mark_read(
    notification_id: str,
    current_user: User = Depends(get_current_user)
):
    from app.models import Notification
    notif = await Notification.get(notification_id)
    if not notif:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    if notif.user_id != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    await NotificationRepository.mark_read(notification_id)
    notif.read_status = True
    return NotificationResponse(**_serialize(notif))


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def mark_all_read(current_user: User = Depends(get_current_user)):
    await NotificationRepository.mark_all_read(str(current_user.id))
