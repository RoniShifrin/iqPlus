"""Search API route"""
from fastapi import APIRouter, Depends, Query
from typing import Optional

from app.models import User, RoleEnum
from app.schemas import SearchResponse, SearchResult
from app.security import get_current_user
from app.repositories import CourseRepository, UserRepository

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("/", response_model=SearchResponse)
async def search(
    q: str = Query("", max_length=100),
    type: Optional[str] = Query(None, pattern="^(courses|students|teachers)$"),
    current_user: User = Depends(get_current_user)
):
    # Allow empty q only for admin/teacher listing all of a specific type.
    # Require at least 1 char for untyped or public searches.
    if not q and type is None:
        return SearchResponse(query=q, results=[], total=0)
    q_lower = q.strip().lower()
    results: list[SearchResult] = []

    search_courses = type in (None, "courses")
    search_students = type in (None, "students") and current_user.role in (RoleEnum.ADMIN, RoleEnum.TEACHER)
    search_teachers = type in (None, "teachers") and current_user.role == RoleEnum.ADMIN

    if search_courses:
        from app.models import CourseStatusEnum, VisibilityScopeEnum
        all_courses = await CourseRepository.list_all()
        for c in all_courses:
            # Mirror visibility rules from GET /api/courses/
            if current_user.role == RoleEnum.ADMIN:
                pass
            elif current_user.role == RoleEnum.TEACHER:
                if c.teacher_id != str(current_user.id):
                    if c.status != CourseStatusEnum.PUBLISHED:
                        continue
                    if c.visibility_scope == VisibilityScopeEnum.TEACHER_ONLY:
                        continue
            elif current_user.role == RoleEnum.STUDENT:
                if c.status != CourseStatusEnum.PUBLISHED:
                    continue
                if c.visibility_scope == VisibilityScopeEnum.TEACHER_ONLY:
                    continue
            else:  # PARENT — mirrors GET /api/courses/ parent branch
                if c.status != CourseStatusEnum.PUBLISHED:
                    continue
                if c.visibility_scope == VisibilityScopeEnum.TEACHER_ONLY:
                    continue

            if q_lower in c.name.lower() or q_lower in c.code.lower() or (c.description and q_lower in c.description.lower()):
                results.append(SearchResult(
                    type="course",
                    id=str(c.id),
                    title=c.name,
                    subtitle=c.code,
                    status=c.status
                ))

    if search_students:
        students = await UserRepository.list_by_role(RoleEnum.STUDENT)
        for s in students:
            name = s.full_name()
            if not q_lower or q_lower in name.lower() or q_lower in s.email.lower():
                results.append(SearchResult(
                    type="student",
                    id=str(s.id),
                    title=name,
                    subtitle=s.email
                ))

    if search_teachers:
        teachers = await UserRepository.list_by_role(RoleEnum.TEACHER)
        for t in teachers:
            name = t.full_name()
            if not q_lower or q_lower in name.lower() or q_lower in t.email.lower():
                results.append(SearchResult(
                    type="teacher",
                    id=str(t.id),
                    title=name,
                    subtitle=t.email
                ))

    return SearchResponse(query=q, results=results, total=len(results))
