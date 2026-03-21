"""Admin user management routes — list, deactivate, activate, soft-delete, view courses."""
import secrets
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, status
from passlib.context import CryptContext

from app.models import User, RoleEnum, EnrollmentStatusEnum
from app.security import get_current_user
from app.repositories import (
    UserRepository, EnrollmentRepository, CourseRepository, AuditLogRepository,
)

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

router = APIRouter(prefix="/api/admin/users", tags=["admin-users"])


def _serialize_user(u: User) -> dict:
    role_val = u.role.value if hasattr(u.role, "value") else u.role
    approved_at = getattr(u, "approved_at", None)
    return {
        "id": str(u.id),
        "email": u.email,
        "first_name": u.first_name or "",
        "last_name": u.last_name or "",
        "display_name": u.display_name or u.full_name(),
        "role": role_val,
        "is_active": u.is_active,
        "is_approved": getattr(u, "is_approved", True),
        "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
        "last_active_at": u.last_active_at.isoformat() if u.last_active_at else None,
        "approved_at": approved_at.isoformat() if approved_at else None,
        "deleted_at": u.deleted_at.isoformat() if u.deleted_at else None,
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }


def _require_admin(current_user: User) -> None:
    if current_user.role != RoleEnum.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")


# ── GET /api/admin/users/ ──────────────────────────────────────────────────────
@router.get("/")
async def list_users(
    role: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    """List all non-deleted users, optionally filtered by role."""
    _require_admin(current_user)
    if role:
        try:
            role_enum = RoleEnum(role)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid role: {role}")
        users = await User.find(
            User.role == role_enum,
            User.deleted_at == None,  # noqa: E711
        ).to_list()
    else:
        users = await User.find(User.deleted_at == None).to_list()  # noqa: E711
    return [_serialize_user(u) for u in users]


# ── GET /api/admin/users/pending ──────────────────────────────────────────────
@router.get("/pending")
async def list_pending_users(
    current_user: User = Depends(get_current_user),
):
    """Return all users whose accounts are awaiting admin approval."""
    _require_admin(current_user)
    users = await User.find(
        User.is_approved == False,  # noqa: E712
        User.deleted_at == None,     # noqa: E711
    ).to_list()
    return [_serialize_user(u) for u in users]


# ── POST /api/admin/users/create ───────────────────────────────────────────────
@router.post("/create")
async def create_user(
    body: dict,
    current_user: User = Depends(get_current_user),
):
    """Admin: manually create a user (pre-approved, immediately active)."""
    _require_admin(current_user)

    email = (body.get("email") or "").strip().lower()
    first_name = (body.get("first_name") or "").strip()
    last_name = (body.get("last_name") or "").strip()
    password = body.get("password") or ""
    role_str = (body.get("role") or "student").strip().lower()

    if not email or not first_name or not last_name:
        raise HTTPException(status_code=400, detail="email, first_name, and last_name are required")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    allowed_roles = {"student", "teacher", "parent"}
    if role_str not in allowed_roles:
        raise HTTPException(
            status_code=400,
            detail=f"Role must be one of: {', '.join(sorted(allowed_roles))}",
        )

    existing = await UserRepository.get_by_email(email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    role = RoleEnum(role_str)
    now = datetime.utcnow()
    new_user = User(
        firebase_uid=email,
        email=email,
        first_name=first_name,
        last_name=last_name,
        role=role,
        hashed_password=_pwd_ctx.hash(password),
        session_token=None,
        is_active=True,
        is_approved=True,    # admin-created users are pre-approved
        approved_at=now,
    )
    await new_user.insert()

    await AuditLogRepository.log(
        user_id=str(current_user.id),
        action="user_created_by_admin",
        resource_type="user",
        resource_id=str(new_user.id),
        details={"email": email, "role": role_str},
    )
    return _serialize_user(new_user)


# ── PATCH /api/admin/users/{user_id}/approve ──────────────────────────────────
@router.patch("/{user_id}/approve")
async def approve_user(
    user_id: str,
    body: Optional[dict] = Body(default=None),
    current_user: User = Depends(get_current_user),
):
    """Approve a pending registration. Optionally correct the user's role before approving."""
    _require_admin(current_user)

    user = await UserRepository.get_by_id(user_id)
    if not user or user.deleted_at is not None:
        raise HTTPException(status_code=404, detail="User not found")
    if getattr(user, "is_approved", True):
        raise HTTPException(status_code=400, detail="User is already approved")

    # Allow admin to correct the requested role before approving
    new_role = user.role
    role_str = ((body or {}).get("role") or "").strip().lower()
    if role_str and role_str in {"student", "teacher", "parent"}:
        new_role = RoleEnum(role_str)

    now = datetime.utcnow()
    await user.set({
        "is_approved": True,
        "is_active": True,
        "role": new_role,
        "approved_at": now,
        "updated_at": now,
    })

    old_role = user.role.value if hasattr(user.role, "value") else user.role
    await AuditLogRepository.log(
        user_id=str(current_user.id),
        action="user_approved",
        resource_type="user",
        resource_id=user_id,
        details={"email": user.email, "role": new_role.value if hasattr(new_role, "value") else new_role, "previous_role": old_role},
    )
    return _serialize_user(user)


# ── PATCH /api/admin/users/{user_id}/reject ───────────────────────────────────
@router.patch("/{user_id}/reject")
async def reject_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
):
    """Reject a pending registration. The account remains inactive."""
    _require_admin(current_user)

    user = await UserRepository.get_by_id(user_id)
    if not user or user.deleted_at is not None:
        raise HTTPException(status_code=404, detail="User not found")
    if getattr(user, "is_approved", True):
        raise HTTPException(status_code=400, detail="User is already approved; use deactivate to restrict access")

    now = datetime.utcnow()
    await user.set({"is_active": False, "deleted_at": now, "updated_at": now})

    await AuditLogRepository.log(
        user_id=str(current_user.id),
        action="user_rejected",
        resource_type="user",
        resource_id=user_id,
        details={"email": user.email, "role": user.role.value if hasattr(user.role, "value") else user.role},
    )
    return {"id": user_id, "rejected": True}


# ── PATCH /api/admin/users/{user_id}/deactivate ────────────────────────────────
@router.patch("/{user_id}/deactivate")
async def deactivate_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
):
    """Deactivate a user: sets is_active=False and invalidates session token."""
    _require_admin(current_user)
    if user_id == str(current_user.id):
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")

    user = await UserRepository.get_by_id(user_id)
    if not user or user.deleted_at is not None:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="User is already inactive")

    await user.set({"is_active": False, "session_token": None, "updated_at": datetime.utcnow()})

    await AuditLogRepository.log(
        user_id=str(current_user.id),
        action="user_deactivated",
        resource_type="user",
        resource_id=user_id,
        details={"email": user.email, "role": user.role.value if hasattr(user.role, "value") else user.role},
    )
    return {"id": user_id, "is_active": False}


# ── PATCH /api/admin/users/{user_id}/activate ──────────────────────────────────
@router.patch("/{user_id}/activate")
async def activate_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
):
    """Re-activate a previously deactivated user."""
    _require_admin(current_user)

    user = await UserRepository.get_by_id(user_id)
    if not user or user.deleted_at is not None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.is_active:
        raise HTTPException(status_code=400, detail="User is already active")

    await user.set({"is_active": True, "updated_at": datetime.utcnow()})

    await AuditLogRepository.log(
        user_id=str(current_user.id),
        action="user_activated",
        resource_type="user",
        resource_id=user_id,
        details={"email": user.email},
    )
    return {"id": user_id, "is_active": True}


# ── DELETE /api/admin/users/{user_id} ─────────────────────────────────────────
@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
):
    """Soft-delete a user: sets deleted_at=now and is_active=False.

    Grades, feedback, enrollments, and audit logs are preserved.
    The user cannot log in after deletion.
    """
    _require_admin(current_user)
    if user_id == str(current_user.id):
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    user = await UserRepository.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.deleted_at is not None:
        raise HTTPException(status_code=400, detail="User is already deleted")

    now = datetime.utcnow()
    await user.set({
        "deleted_at": now,
        "is_active": False,
        "session_token": None,
        "updated_at": now,
    })

    await AuditLogRepository.log(
        user_id=str(current_user.id),
        action="user_deleted",
        resource_type="user",
        resource_id=user_id,
        details={"email": user.email, "role": user.role.value if hasattr(user.role, "value") else user.role},
    )
    return {"id": user_id, "deleted": True}


# ── GET /api/admin/users/{user_id}/courses ────────────────────────────────────
@router.get("/{user_id}/courses")
async def get_user_courses(
    user_id: str,
    current_user: User = Depends(get_current_user),
):
    """Return courses associated with a user.

    - Student → enrollments (all statuses)
    - Teacher → courses they own
    """
    _require_admin(current_user)

    user = await UserRepository.get_by_id(user_id)
    if not user or user.deleted_at is not None:
        raise HTTPException(status_code=404, detail="User not found")

    role_val = user.role.value if hasattr(user.role, "value") else user.role

    if role_val == "student":
        enrollments = await EnrollmentRepository.list_by_student(user_id)
        result = []
        for enr in enrollments:
            course = await CourseRepository.get_by_id(enr.course_id)
            if course and course.deleted_at is None:
                enr_status = enr.status.value if hasattr(enr.status, "value") else enr.status
                result.append({
                    "course_id": enr.course_id,
                    "course_name": course.name,
                    "course_code": course.code,
                    "enrollment_id": str(enr.id),
                    "enrollment_status": enr_status,
                })
        return result

    if role_val == "teacher":
        courses = await CourseRepository.list_by_teacher(user_id)
        return [{
            "course_id": str(c.id),
            "course_name": c.name,
            "course_code": c.code,
            "status": c.status.value if hasattr(c.status, "value") else c.status,
        } for c in courses]

    return []


# ── PATCH /api/admin/users/{user_id}/role ─────────────────────────────────────
@router.patch("/{user_id}/role")
async def change_user_role(
    user_id: str,
    body: dict,
    current_user: User = Depends(get_current_user),
):
    """Admin: change a user's role (e.g. promote student → teacher or demote teacher → student).

    Safety checks:
    - Cannot change own role (no self-demotion).
    - Cannot remove the last admin from the system.
    - Target user must not be deleted.
    - Only student ↔ teacher role changes are permitted via this endpoint.
    """
    _require_admin(current_user)

    if user_id == str(current_user.id):
        raise HTTPException(status_code=400, detail="Cannot change your own role")

    user = await UserRepository.get_by_id(user_id)
    if not user or user.deleted_at is not None:
        raise HTTPException(status_code=404, detail="User not found")

    new_role_str = body.get("role", "").strip().lower()
    allowed_roles = {"student", "teacher", "parent"}
    if new_role_str not in allowed_roles:
        raise HTTPException(
            status_code=400,
            detail=f"Role must be one of: {', '.join(sorted(allowed_roles))}. "
                   "Admin role cannot be assigned via this endpoint.",
        )

    try:
        new_role = RoleEnum(new_role_str)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid role: {new_role_str}")

    old_role = user.role.value if hasattr(user.role, "value") else user.role

    # Guard: do not demote the last admin
    if old_role == "admin":
        admin_count = await User.find(
            User.role == RoleEnum.ADMIN,
            User.deleted_at == None,  # noqa: E711
        ).count()
        if admin_count <= 1:
            raise HTTPException(
                status_code=400,
                detail="Cannot demote the last admin in the system",
            )

    if old_role == new_role_str:
        raise HTTPException(status_code=400, detail=f"User already has role '{new_role_str}'")

    await user.set({"role": new_role, "updated_at": datetime.utcnow()})

    await AuditLogRepository.log(
        user_id=str(current_user.id),
        action="user_role_changed",
        resource_type="user",
        resource_id=user_id,
        details={"email": user.email, "old_role": old_role, "new_role": new_role_str},
    )
    return {"id": user_id, "role": new_role_str, "email": user.email}
