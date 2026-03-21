"""Syllabus Builder routes.

POST /api/syllabus/                              — create syllabus (teacher/admin)
GET  /api/syllabus/{course_id}                   — get syllabus for a course
PUT  /api/syllabus/{syllabus_id}                 — update (teacher/admin)
PUT  /api/syllabus/{syllabus_id}/publish         — publish (teacher/admin)
GET  /api/syllabus/{course_id}/milestones        — upcoming milestones (student/parent friendly)
POST /api/syllabus/{syllabus_id}/complete-week   — mark a week complete (teacher/admin)
"""
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from app.models import User, RoleEnum, Syllabus, SyllabusStatusEnum, WeeklyTopic
from app.schemas import SyllabusCreate, SyllabusUpdate, SyllabusResponse, WeeklyTopicSchema, MilestoneCompleteRequest
from app.security import get_current_user
from app.repositories import SyllabusRepository, CourseRepository

router = APIRouter(prefix="/api/syllabus", tags=["syllabus"])


def _topic_to_schema(t: WeeklyTopic, hide_teacher_notes: bool = False) -> WeeklyTopicSchema:
    return WeeklyTopicSchema(
        week_number=t.week_number,
        title=t.title,
        description=t.description,
        objectives=t.objectives,
        materials=t.materials,
        assignments=getattr(t, "assignments", []),
        teacher_notes=None if hide_teacher_notes else getattr(t, "teacher_notes", None),
    )


def _serialize(s: Syllabus, hide_teacher_notes: bool = False) -> dict:
    return {
        "id": str(s.id),
        "course_id": s.course_id,
        "version": s.version,
        "status": s.status.value if hasattr(s.status, "value") else s.status,
        "topics": [_topic_to_schema(t, hide_teacher_notes).model_dump() for t in s.topics],
        "completed_weeks": getattr(s, "completed_weeks", []),
        "created_by": s.created_by,
        "created_at": s.created_at,
        "updated_at": s.updated_at,
    }


@router.post("/", response_model=SyllabusResponse, status_code=status.HTTP_201_CREATED)
async def create_syllabus(
    body: SyllabusCreate,
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in (RoleEnum.TEACHER, RoleEnum.ADMIN):
        raise HTTPException(status_code=403, detail="Teachers and admins only")

    course = await CourseRepository.get_by_id(body.course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    if course.teacher_id != str(current_user.id) and current_user.role != RoleEnum.ADMIN:
        raise HTTPException(status_code=403, detail="Not your course")

    existing = await SyllabusRepository.get_by_course(body.course_id)
    if existing:
        raise HTTPException(
            status_code=409,
            detail="Syllabus already exists for this course. Use PUT to update.",
        )

    topics = [
        WeeklyTopic(
            week_number=t.week_number,
            title=t.title,
            description=t.description,
            objectives=t.objectives,
            materials=t.materials,
            assignments=t.assignments,
            teacher_notes=t.teacher_notes,
        )
        for t in body.topics
    ]
    syllabus = await SyllabusRepository.create(
        course_id=body.course_id,
        topics=topics,
        created_by=str(current_user.id),
    )
    return SyllabusResponse(**_serialize(syllabus))


@router.get("/{course_id}", response_model=SyllabusResponse)
async def get_syllabus(
    course_id: str,
    current_user: User = Depends(get_current_user),
):
    syllabus = await SyllabusRepository.get_by_course(course_id)
    if not syllabus:
        raise HTTPException(status_code=404, detail="Syllabus not found")

    hide_notes = current_user.role in (RoleEnum.STUDENT, RoleEnum.PARENT)

    # Students and parents can only see published syllabi
    if hide_notes and syllabus.status != SyllabusStatusEnum.PUBLISHED:
        raise HTTPException(status_code=404, detail="Syllabus not published yet")

    return SyllabusResponse(**_serialize(syllabus, hide_teacher_notes=hide_notes))


@router.get("/{course_id}/milestones")
async def get_milestones(
    course_id: str,
    current_user: User = Depends(get_current_user),
):
    """Upcoming milestones for a course — student/parent friendly (teacher_notes hidden)."""
    syllabus = await SyllabusRepository.get_by_course(course_id)
    if not syllabus:
        raise HTTPException(status_code=404, detail="Syllabus not found")

    hide_notes = current_user.role in (RoleEnum.STUDENT, RoleEnum.PARENT)
    if hide_notes and syllabus.status != SyllabusStatusEnum.PUBLISHED:
        raise HTTPException(status_code=404, detail="Syllabus not published yet")

    completed = set(getattr(syllabus, "completed_weeks", []))
    milestones = []
    for t in sorted(syllabus.topics, key=lambda x: x.week_number):
        milestones.append({
            **_topic_to_schema(t, hide_teacher_notes=hide_notes).model_dump(),
            "completed": t.week_number in completed,
        })
    return {"course_id": course_id, "milestones": milestones}


@router.post("/{syllabus_id}/complete-week", response_model=SyllabusResponse)
async def complete_week(
    syllabus_id: str,
    body: MilestoneCompleteRequest,
    current_user: User = Depends(get_current_user),
):
    """Teacher marks a specific week as completed."""
    if current_user.role not in (RoleEnum.TEACHER, RoleEnum.ADMIN):
        raise HTTPException(status_code=403, detail="Teachers and admins only")

    syllabus = await SyllabusRepository.get_by_id(syllabus_id)
    if not syllabus:
        raise HTTPException(status_code=404, detail="Syllabus not found")

    course = await CourseRepository.get_by_id(syllabus.course_id)
    if course and course.teacher_id != str(current_user.id) and current_user.role != RoleEnum.ADMIN:
        raise HTTPException(status_code=403, detail="Not your course")

    completed = list(set(getattr(syllabus, "completed_weeks", []) + [body.week_number]))
    now = datetime.utcnow()
    await syllabus.set({"completed_weeks": completed, "updated_at": now})
    # Refresh local object so the response reflects the committed state
    syllabus.completed_weeks = completed
    syllabus.updated_at = now
    return SyllabusResponse(**_serialize(syllabus))


@router.put("/{syllabus_id}", response_model=SyllabusResponse)
async def update_syllabus(
    syllabus_id: str,
    body: SyllabusUpdate,
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in (RoleEnum.TEACHER, RoleEnum.ADMIN):
        raise HTTPException(status_code=403, detail="Teachers and admins only")

    syllabus = await SyllabusRepository.get_by_id(syllabus_id)
    if not syllabus:
        raise HTTPException(status_code=404, detail="Syllabus not found")

    course = await CourseRepository.get_by_id(syllabus.course_id)
    if course and course.teacher_id != str(current_user.id) and current_user.role != RoleEnum.ADMIN:
        raise HTTPException(status_code=403, detail="Not your course")

    updates: dict = {"updated_at": datetime.utcnow()}
    if body.topics is not None:
        updates["topics"] = [
            WeeklyTopic(
                week_number=t.week_number,
                title=t.title,
                description=t.description,
                objectives=t.objectives,
                materials=t.materials,
                assignments=t.assignments,
                teacher_notes=t.teacher_notes,
            )
            for t in body.topics
        ]
    if body.status is not None:
        updates["status"] = SyllabusStatusEnum(body.status)

    await syllabus.set(updates)
    # Refresh local object so the response reflects the committed state
    for k, v in updates.items():
        try:
            setattr(syllabus, k, v)
        except Exception:
            pass
    return SyllabusResponse(**_serialize(syllabus))


@router.put("/{syllabus_id}/publish", response_model=SyllabusResponse)
async def publish_syllabus(
    syllabus_id: str,
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in (RoleEnum.TEACHER, RoleEnum.ADMIN):
        raise HTTPException(status_code=403, detail="Teachers and admins only")

    syllabus = await SyllabusRepository.get_by_id(syllabus_id)
    if not syllabus:
        raise HTTPException(status_code=404, detail="Syllabus not found")

    course = await CourseRepository.get_by_id(syllabus.course_id)
    if course and course.teacher_id != str(current_user.id) and current_user.role != RoleEnum.ADMIN:
        raise HTTPException(status_code=403, detail="Not your course")

    now = datetime.utcnow()
    await syllabus.set({
        "status": SyllabusStatusEnum.PUBLISHED,
        "updated_at": now,
    })
    # Refresh local object so the response reflects the committed state
    syllabus.status = SyllabusStatusEnum.PUBLISHED
    syllabus.updated_at = now
    return SyllabusResponse(**_serialize(syllabus))
