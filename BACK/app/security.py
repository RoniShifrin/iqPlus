"""Security, authentication, and RBAC"""
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import firebase_admin
from firebase_admin import credentials, auth
import os
import logging

from app.models import User, RoleEnum

logger = logging.getLogger(__name__)

# Initialize Firebase (optional — only used when Firebase credentials are present)
try:
    if not firebase_admin.get_app():
        firebase_key_path = os.getenv('FIREBASE_KEY_PATH', '.firebase/serviceAccountKey.json')
        if os.path.exists(firebase_key_path):
            cred = credentials.Certificate(firebase_key_path)
            firebase_admin.initialize_app(cred)
except ValueError:
    logger.warning("Firebase app already initialized or not configured")

security = HTTPBearer(auto_error=False)


async def verify_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> dict:
    """
    Resolve a Bearer token to a uid/email dict.

    Resolution order:
      1. Opaque session token issued by /api/auth/login  (primary, all new accounts)
      2. Firebase ID token                               (fallback for Firebase-managed accounts)
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
        )

    token = credentials.credentials

    # ── 1. Session token (issued by login endpoint) ──────────────────────────
    user = await User.find_one(
        User.session_token == token,
        User.deleted_at == None,
    )
    if user:
        return {"uid": user.firebase_uid, "email": user.email}

    # ── 2. Firebase ID token fallback ────────────────────────────────────────
    try:
        decoded = auth.verify_id_token(token)
        return decoded
    except Exception as e:
        logger.debug("Firebase token verification failed: %s", e)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token",
    )


# Alias so existing route imports that use verify_firebase_token are not broken
verify_firebase_token = verify_token


async def get_current_user(
    token: dict = Depends(verify_token)
) -> User:
    """Get authenticated user from resolved token dict."""
    firebase_uid = token.get("uid")

    user = await User.find_one(
        User.firebase_uid == firebase_uid,
        User.deleted_at == None,
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    return user


def require_role(*roles: RoleEnum):
    """Dependency factory to require specific roles."""
    async def check_role(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role}' is not authorized for this action",
            )
        return current_user
    return check_role


async def get_teacher_user(
    current_user: User = Depends(get_current_user)
) -> User:
    if current_user.role not in [RoleEnum.TEACHER, RoleEnum.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Teacher access required",
        )
    return current_user


async def require_course_owner_or_admin(
    course_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Resolves the course and checks ownership.
    Returns (course, current_user) tuple.
    Raises 404 if not found, 403 if not owner or admin.
    """
    from app.repositories import CourseRepository

    try:
        course = await CourseRepository.get_by_id(course_id)
    except Exception:
        course = None

    if not course or course.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    if current_user.role == RoleEnum.ADMIN:
        return course, current_user

    if current_user.role != RoleEnum.TEACHER or course.teacher_id != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not the owner of this course",
        )

    return course, current_user
