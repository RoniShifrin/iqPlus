"""Authentication API routes"""
import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from passlib.context import CryptContext

from app.models import User, RoleEnum
from app.schemas import UserResponse, LoginRequest, SignupRequest, TokenResponse
from app.security import get_current_user
from app.repositories import UserRepository

router = APIRouter(prefix="/api/auth", tags=["authentication"])

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _hash(raw: str) -> str:
    return _pwd.hash(raw)


def _verify(raw: str, hashed: str) -> bool:
    return _pwd.verify(raw, hashed)


def _issue_token() -> str:
    return secrets.token_urlsafe(32)


def _serialize_user(user: User) -> dict:
    return {
        "id":                 str(user.id),
        "firebase_uid":       user.firebase_uid,
        "email":              user.email,
        "first_name":         user.first_name,
        "last_name":          user.last_name,
        "display_name":       user.display_name,
        "role":               user.role,
        "avatar_url":         user.avatar_url,
        "linked_student_ids": user.linked_student_ids or [],
        "is_active":          user.is_active,
        "is_approved":        getattr(user, "is_approved", True),
        "created_at":         user.created_at,
    }


@router.post("/signup")
async def signup(request: SignupRequest):
    existing = await UserRepository.get_by_email(request.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    role_map = {
        "teacher": RoleEnum.TEACHER, "TEACHER": RoleEnum.TEACHER,
        "student": RoleEnum.STUDENT, "STUDENT": RoleEnum.STUDENT,
        "parent":  RoleEnum.PARENT,  "PARENT":  RoleEnum.PARENT,
    }
    role = role_map.get(request.role, RoleEnum.STUDENT)

    try:
        new_user = User(
            firebase_uid=request.email,
            email=request.email,
            first_name=request.first_name,
            last_name=request.last_name,
            role=role,
            hashed_password=_hash(request.password),
            is_active=False,    # not active until admin approves
            is_approved=False,  # pending admin approval
        )
        await new_user.insert()
        return JSONResponse(
            status_code=202,
            content={
                "status": "pending",
                "message": (
                    "Registration submitted. An administrator will review your account. "
                    "You will be able to log in once approved."
                ),
            },
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registration failed",
        )


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    user = await UserRepository.get_by_email(request.email)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    # Approval check before is_active — new signups have is_active=False until approved,
    # so without this ordering they would receive the generic "Invalid credentials" message
    # instead of the helpful "pending approval" message.
    if not getattr(user, "is_approved", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account pending admin approval. Please wait for an administrator to review your registration.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    if not user.hashed_password or not _verify(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    token = _issue_token()
    await user.set({User.session_token: token, "last_login_at": datetime.utcnow()})
    return TokenResponse(access_token=token, token_type="bearer")


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    return UserResponse(**_serialize_user(current_user))


@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    """Invalidate the current session token."""
    await current_user.set({User.session_token: None})
    return {"message": "Logged out successfully"}


@router.post("/refresh-token", response_model=TokenResponse)
async def refresh_token(current_user: User = Depends(get_current_user)):
    """Issue a fresh session token."""
    token = _issue_token()
    await current_user.set({User.session_token: token})
    return TokenResponse(access_token=token, token_type="bearer")
