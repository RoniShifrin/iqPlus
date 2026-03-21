"""User profile endpoints — GET/PUT /api/me/profile, POST /api/me/avatar, GET /api/users/{id}/profile"""
import os
import uuid
from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from bson import ObjectId

from app.models import User, RoleEnum, Course, Enrollment, EnrollmentStatusEnum
from app.schemas import UserResponse, ProfileUpdate, AvatarResponse
from app.security import get_current_user
from app.repositories import UserRepository

router = APIRouter(prefix="/api/me", tags=["profile"])
users_router = APIRouter(prefix="/api/users", tags=["users"])

UPLOAD_DIR = Path(__file__).resolve().parents[4] / "uploads" / "avatars"
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_SIZE_BYTES = 2 * 1024 * 1024  # 2 MB


def _serialize(user: User) -> dict:
    role = user.role
    if hasattr(role, "value"):
        role = role.value
    else:
        role = str(role) if role else "student"
    return {
        "id": str(user.id),
        "firebase_uid": user.firebase_uid or None,
        "email": user.email or "",
        "first_name": user.first_name,
        "last_name": user.last_name,
        "display_name": user.display_name,
        "role": role,
        "avatar_url": user.avatar_url,
        "age": getattr(user, "age", None),
        "linked_student_ids": user.linked_student_ids or [],
        "is_active": bool(user.is_active) if user.is_active is not None else True,
        "created_at": user.created_at or datetime.utcnow(),
        "courses": [],
    }


def _course_to_dict(c: Course) -> dict:
    status_val = c.status.value if hasattr(c.status, "value") else str(c.status)
    scope_val = c.visibility_scope.value if hasattr(c.visibility_scope, "value") else str(c.visibility_scope)
    return {
        "id": str(c.id),
        "code": c.code,
        "name": c.name,
        "description": c.description,
        "status": status_val,
        "visibility_scope": scope_val,
        "capacity": c.capacity,
        "schedule": c.schedule,
    }


async def _fetch_courses_for(target: User) -> list:
    """Fetch courses relevant to the target user's role. Never raises."""
    try:
        target_id = str(target.id)
        role = target.role
        if hasattr(role, "value"):
            role = role.value

        if role == "teacher":
            courses = await Course.find(
                Course.teacher_id == target_id,
                Course.deleted_at == None,  # noqa: E711
            ).to_list()
            return [_course_to_dict(c) for c in courses]

        if role == "student":
            enrollments = await Enrollment.find(
                Enrollment.student_id == target_id,
                Enrollment.status == EnrollmentStatusEnum.ACTIVE,
            ).to_list()
            if not enrollments:
                return []
            course_ids = [ObjectId(e.course_id) for e in enrollments if e.course_id]
            courses = await Course.find(
                {"_id": {"$in": course_ids}, "deleted_at": None}
            ).to_list()
            return [_course_to_dict(c) for c in courses]

        if role == "parent":
            child_ids = target.linked_student_ids or []
            if not child_ids:
                return []
            enrollments = await Enrollment.find(
                {"student_id": {"$in": child_ids}, "status": EnrollmentStatusEnum.ACTIVE},
            ).to_list()
            if not enrollments:
                return []
            course_ids = list({ObjectId(e.course_id) for e in enrollments if e.course_id})
            courses = await Course.find(
                {"_id": {"$in": course_ids}, "deleted_at": None}
            ).to_list()
            return [_course_to_dict(c) for c in courses]

    except Exception:
        pass
    return []


@router.get("/profile", response_model=UserResponse)
async def get_profile(current_user: User = Depends(get_current_user)):
    data = _serialize(current_user)
    data["courses"] = await _fetch_courses_for(current_user)
    return UserResponse(**data)


@router.put("/profile", response_model=UserResponse)
async def update_profile(
    body: ProfileUpdate,
    current_user: User = Depends(get_current_user),
):
    updates: dict = {"updated_at": datetime.utcnow()}
    if body.display_name is not None:
        updates["display_name"] = body.display_name
    if body.first_name is not None:
        updates["first_name"] = body.first_name
    if body.last_name is not None:
        updates["last_name"] = body.last_name
    if body.age is not None:
        updates["age"] = body.age
    await current_user.set(updates)
    return UserResponse(**_serialize(current_user))


@router.post("/avatar", response_model=AvatarResponse)
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    # Validate type
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type '{file.content_type}'. Allowed: jpg, png, webp",
        )

    # Read and validate size
    contents = await file.read()
    if len(contents) > MAX_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds 2 MB limit",
        )

    # Determine extension
    ext_map = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
    ext = ext_map[file.content_type]

    # Use uid-based filename so re-uploads replace the old one
    safe_uid = current_user.firebase_uid.replace("@", "_at_").replace(".", "_")
    filename = f"{safe_uid}.{ext}"

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    dest = UPLOAD_DIR / filename
    dest.write_bytes(contents)

    avatar_url = f"/uploads/avatars/{filename}"
    await current_user.set({"avatar_url": avatar_url, "updated_at": datetime.utcnow()})

    return AvatarResponse(avatar_url=avatar_url)


@users_router.get("/{user_id}/profile", response_model=UserResponse)
async def get_user_profile(
    user_id: str,
    current_user: User = Depends(get_current_user),
):
    """View another user's public profile (role-gated)."""
    # Own profile: return directly without extra DB lookup
    if user_id == str(current_user.id):
        data = _serialize(current_user)
        data["courses"] = await _fetch_courses_for(current_user)
        return UserResponse(**data)

    try:
        target = await UserRepository.get_by_id(user_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    role = current_user.role
    if role == RoleEnum.ADMIN:
        pass  # admin can view anyone
    elif role == RoleEnum.TEACHER:
        # Teachers can view students and other teachers
        if target.role not in (RoleEnum.STUDENT, RoleEnum.TEACHER):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    elif role == RoleEnum.PARENT:
        # Parents can only view their linked children
        if user_id not in (current_user.linked_student_ids or []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    elif role == RoleEnum.STUDENT:
        # Students can view teachers
        if target.role != RoleEnum.TEACHER:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    data = _serialize(target)
    data["courses"] = await _fetch_courses_for(target)
    return UserResponse(**data)
