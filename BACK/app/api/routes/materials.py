"""Course Materials API routes"""
import os
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from typing import List, Optional

from app.models import User, RoleEnum
from app.schemas import CourseMaterialCreate, CourseMaterialResponse
from app.security import get_current_user
from app.repositories import (
    CourseMaterialRepository, CourseRepository, EnrollmentRepository, AuditLogRepository
)
from app.models import EnrollmentStatusEnum

router = APIRouter(prefix="/api/courses", tags=["materials"])

MATERIALS_DIR = Path(__file__).resolve().parents[3] / "uploads" / "materials"
MATERIALS_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_TYPES = {"application/pdf", "image/png", "image/jpeg", "application/msword",
                 "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                 "text/plain"}
MAX_SIZE = 10 * 1024 * 1024  # 10 MB


def _serialize(m) -> dict:
    return {
        "id": str(m.id),
        "course_id": m.course_id,
        "title": m.title,
        "file_url": m.file_url,
        "link_url": m.link_url,
        "uploaded_by": m.uploaded_by,
        "created_at": m.created_at,
    }


async def _check_course_access(course_id: str, user: User) -> None:
    """Raise 403/404 if user cannot access this course's materials."""
    course = await CourseRepository.get_by_id(course_id)
    if not course or course.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    if user.role == RoleEnum.ADMIN:
        return
    if user.role == RoleEnum.TEACHER and course.teacher_id == str(user.id):
        return
    if user.role == RoleEnum.STUDENT:
        enrollment = await EnrollmentRepository.get_by_student_course(str(user.id), course_id)
        if enrollment and enrollment.status == EnrollmentStatusEnum.ACTIVE:
            return
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enrolled in this course")
    if user.role == RoleEnum.PARENT:
        # Parents may view materials for courses any of their linked children are enrolled in
        for child_id in (user.linked_student_ids or []):
            enrollment = await EnrollmentRepository.get_by_student_course(child_id, course_id)
            if enrollment and enrollment.status == EnrollmentStatusEnum.ACTIVE:
                return
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No linked child enrolled in this course")
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")


@router.get("/{course_id}/materials", response_model=List[CourseMaterialResponse])
async def list_materials(
    course_id: str,
    current_user: User = Depends(get_current_user)
):
    await _check_course_access(course_id, current_user)
    materials = await CourseMaterialRepository.list_by_course(course_id)
    return [CourseMaterialResponse(**_serialize(m)) for m in materials]


@router.post("/{course_id}/materials", response_model=CourseMaterialResponse, status_code=status.HTTP_201_CREATED)
async def add_material(
    course_id: str,
    title: str = Form(...),
    link_url: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user)
):
    course = await CourseRepository.get_by_id(course_id)
    if not course or course.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    is_owner = current_user.role == RoleEnum.TEACHER and course.teacher_id == str(current_user.id)
    if current_user.role != RoleEnum.ADMIN and not is_owner:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    if not title.strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Title is required")

    file_url = None
    if file and file.filename:
        if file.content_type and file.content_type not in ALLOWED_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File type '{file.content_type}' not allowed. Allowed: PDF, Word, images, plain text.",
            )
        content = await file.read()
        if len(content) > MAX_SIZE:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File exceeds 10MB limit")
        ext = Path(file.filename).suffix.lower()
        safe_name = f"{uuid.uuid4().hex}{ext}"
        dest = MATERIALS_DIR / safe_name
        dest.write_bytes(content)
        file_url = f"/uploads/materials/{safe_name}"

    material = await CourseMaterialRepository.create(
        course_id=course_id,
        title=title.strip(),
        file_url=file_url,
        link_url=link_url,
        uploaded_by=str(current_user.id)
    )

    await AuditLogRepository.log(
        user_id=str(current_user.id),
        action="material_added",
        resource_type="course_material",
        resource_id=str(material.id),
        details={"course_id": course_id, "title": title}
    )

    return CourseMaterialResponse(**_serialize(material))


@router.delete("/{course_id}/materials/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_material(
    course_id: str,
    material_id: str,
    current_user: User = Depends(get_current_user)
):
    material = await CourseMaterialRepository.get_by_id(material_id)
    if not material or material.course_id != course_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found")

    course = await CourseRepository.get_by_id(course_id)
    is_owner = current_user.role == RoleEnum.TEACHER and course and course.teacher_id == str(current_user.id)
    if current_user.role != RoleEnum.ADMIN and not is_owner:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    if material.file_url:
        file_path = Path(__file__).resolve().parents[3] / material.file_url.lstrip("/")
        if file_path.exists():
            file_path.unlink()

    await CourseMaterialRepository.delete(material_id)
