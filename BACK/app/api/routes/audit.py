"""Audit Log API routes (admin only)"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional

from app.models import User, RoleEnum, AuditLog
from app.schemas import AuditLogResponse
from app.security import get_current_user
from app.repositories import AuditLogRepository

router = APIRouter(prefix="/api/audit-logs", tags=["audit"])


def _serialize(entry) -> dict:
    return {
        "id": str(entry.id),
        "user_id": entry.user_id,
        "action": entry.action,
        "resource_type": entry.resource_type,
        "resource_id": entry.resource_id,
        "details": entry.details,
        "timestamp": entry.timestamp,
    }


@router.get("/", response_model=List[AuditLogResponse])
async def list_audit_logs(
    limit: int = Query(100, ge=1, le=500),
    skip: int = Query(0, ge=0),
    action: Optional[str] = Query(None, description="Filter by action type, e.g. create_lesson_record"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type, e.g. course"),
    user_id: Optional[str] = Query(None, description="Filter by actor user_id"),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != RoleEnum.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")

    # Build filter conditions
    conditions = []
    if action:
        conditions.append(AuditLog.action == action)
    if resource_type:
        conditions.append(AuditLog.resource_type == resource_type)
    if user_id:
        conditions.append(AuditLog.user_id == user_id)

    if conditions:
        logs = await AuditLog.find(*conditions).sort(-AuditLog.timestamp).skip(skip).limit(limit).to_list()
    else:
        logs = await AuditLogRepository.list_all(limit=limit, skip=skip)

    return [AuditLogResponse(**_serialize(e)) for e in logs]
