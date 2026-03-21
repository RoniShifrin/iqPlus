"""
Tests: Syllabus CRUD + Visibility Rules (Area 5)
Covers:
  - Teacher/admin can create, update, publish syllabus
  - Student/parent blocked from create/update
  - Draft syllabus hidden from student and parent (404)
  - Published syllabus visible to student (200)
  - teacher_notes stripped from student/parent responses
  - Duplicate syllabus → 409
  - Milestones endpoint respects same draft/publish rules
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.main import app
from app.security import get_current_user
from app.models import User, RoleEnum, SyllabusStatusEnum


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_user(role: RoleEnum, uid: str = None) -> User:
    u = MagicMock(spec=User)
    u.id = uid or f"id_{role.value}"
    u.email = f"{role.value}@test.com"
    u.role = role
    u.is_active = True
    u.deleted_at = None
    u.full_name = MagicMock(return_value=role.value.title())
    return u


def _make_course(teacher_id="teacher_id", course_id="course_abc"):
    c = MagicMock()
    c.id = course_id
    c.teacher_id = teacher_id
    c.deleted_at = None
    return c


def _make_topic():
    from app.models import WeeklyTopic
    t = MagicMock(spec=WeeklyTopic)
    t.week_number = 1
    t.title = "Intro"
    t.description = "Introduction"
    t.objectives = ["Obj 1"]
    t.materials = []
    t.assignments = ["HW 1"]
    t.teacher_notes = "Private note for teacher only."
    return t


def _make_syllabus(
    syllabus_id="syll_001",
    course_id="course_abc",
    status=SyllabusStatusEnum.DRAFT,
    with_topic=True,
):
    from app.models import Syllabus
    s = MagicMock(spec=Syllabus)
    s.id = syllabus_id
    s.course_id = course_id
    s.version = 1
    s.status = status
    s.topics = [_make_topic()] if with_topic else []
    s.completed_weeks = []
    s.created_by = "teacher_id"
    s.created_at = datetime.utcnow()
    s.updated_at = datetime.utcnow()
    s.set = AsyncMock(return_value=None)
    return s


def _override(user):
    async def _dep():
        return user
    app.dependency_overrides[get_current_user] = _dep


def _clear():
    app.dependency_overrides.clear()


teacher = _make_user(RoleEnum.TEACHER, "teacher_id")
admin   = _make_user(RoleEnum.ADMIN,   "admin_id")
student = _make_user(RoleEnum.STUDENT, "student_id")
parent  = _make_user(RoleEnum.PARENT,  "parent_id")

SYLLABUS_PAYLOAD = {
    "course_id": "course_abc",
    "topics": [
        {
            "week_number": 1,
            "title": "Week 1: Intro",
            "description": "Basics",
            "objectives": ["Understand core concepts"],
            "materials": [],
            "assignments": ["Read chapter 1"],
            "teacher_notes": "Internal: assess prior knowledge",
        }
    ],
}


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


# ══════════════════════════════════════════════════════════════════════════════
# 5a. Create syllabus — RBAC
# ══════════════════════════════════════════════════════════════════════════════

class TestSyllabusCreate:

    def _create(self, client, user, payload=None):
        _override(user)
        course = _make_course(teacher_id=str(teacher.id))
        syllabus = _make_syllabus(status=SyllabusStatusEnum.DRAFT)
        with patch("app.repositories.CourseRepository.get_by_id",
                   new_callable=AsyncMock, return_value=course), \
             patch("app.repositories.SyllabusRepository.get_by_course",
                   new_callable=AsyncMock, return_value=None), \
             patch("app.repositories.SyllabusRepository.create",
                   new_callable=AsyncMock, return_value=syllabus):
            r = client.post("/api/syllabus/", json=payload or SYLLABUS_PAYLOAD)
        _clear()
        return r

    def test_teacher_can_create_syllabus(self, client):
        r = self._create(client, teacher)
        assert r.status_code == 201

    def test_admin_can_create_syllabus_for_any_course(self, client):
        r = self._create(client, admin)
        assert r.status_code == 201

    def test_student_cannot_create_syllabus(self, client):
        r = self._create(client, student)
        assert r.status_code == 403

    def test_parent_cannot_create_syllabus(self, client):
        r = self._create(client, parent)
        assert r.status_code == 403

    def test_other_teacher_cannot_create_for_course_they_dont_own(self, client):
        other = _make_user(RoleEnum.TEACHER, "other_teacher_id")
        _override(other)
        course = _make_course(teacher_id="teacher_id")  # owned by "teacher_id", not other
        with patch("app.repositories.CourseRepository.get_by_id",
                   new_callable=AsyncMock, return_value=course), \
             patch("app.repositories.SyllabusRepository.get_by_course",
                   new_callable=AsyncMock, return_value=None):
            r = client.post("/api/syllabus/", json=SYLLABUS_PAYLOAD)
        _clear()
        assert r.status_code == 403

    def test_duplicate_syllabus_returns_409(self, client):
        _override(teacher)
        course = _make_course(teacher_id=str(teacher.id))
        existing = _make_syllabus()
        with patch("app.repositories.CourseRepository.get_by_id",
                   new_callable=AsyncMock, return_value=course), \
             patch("app.repositories.SyllabusRepository.get_by_course",
                   new_callable=AsyncMock, return_value=existing):
            r = client.post("/api/syllabus/", json=SYLLABUS_PAYLOAD)
        _clear()
        assert r.status_code == 409

    def test_syllabus_for_nonexistent_course_returns_404(self, client):
        _override(teacher)
        with patch("app.repositories.CourseRepository.get_by_id",
                   new_callable=AsyncMock, return_value=None):
            r = client.post("/api/syllabus/", json=SYLLABUS_PAYLOAD)
        _clear()
        assert r.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# 5b. Read syllabus — draft vs published visibility
# ══════════════════════════════════════════════════════════════════════════════

class TestSyllabusVisibility:

    def _get(self, client, user, syllabus):
        _override(user)
        with patch("app.repositories.SyllabusRepository.get_by_course",
                   new_callable=AsyncMock, return_value=syllabus):
            r = client.get("/api/syllabus/course_abc")
        _clear()
        return r

    def test_teacher_can_read_draft_syllabus(self, client):
        syllabus = _make_syllabus(status=SyllabusStatusEnum.DRAFT)
        r = self._get(client, teacher, syllabus)
        assert r.status_code == 200
        assert r.json()["status"] == "draft"

    def test_student_gets_404_for_draft_syllabus(self, client):
        syllabus = _make_syllabus(status=SyllabusStatusEnum.DRAFT)
        r = self._get(client, student, syllabus)
        assert r.status_code == 404

    def test_parent_gets_404_for_draft_syllabus(self, client):
        syllabus = _make_syllabus(status=SyllabusStatusEnum.DRAFT)
        r = self._get(client, parent, syllabus)
        assert r.status_code == 404

    def test_student_can_read_published_syllabus(self, client):
        syllabus = _make_syllabus(status=SyllabusStatusEnum.PUBLISHED)
        r = self._get(client, student, syllabus)
        assert r.status_code == 200

    def test_teacher_notes_hidden_from_student(self, client):
        syllabus = _make_syllabus(status=SyllabusStatusEnum.PUBLISHED)
        r = self._get(client, student, syllabus)
        assert r.status_code == 200
        topics = r.json()["topics"]
        assert len(topics) > 0
        # teacher_notes must be null/absent in the response
        assert topics[0].get("teacher_notes") is None

    def test_teacher_notes_visible_to_teacher(self, client):
        syllabus = _make_syllabus(status=SyllabusStatusEnum.DRAFT)
        r = self._get(client, teacher, syllabus)
        assert r.status_code == 200
        topics = r.json()["topics"]
        assert topics[0]["teacher_notes"] == "Private note for teacher only."

    def test_nonexistent_syllabus_returns_404(self, client):
        _override(teacher)
        with patch("app.repositories.SyllabusRepository.get_by_course",
                   new_callable=AsyncMock, return_value=None):
            r = client.get("/api/syllabus/unknown_course")
        _clear()
        assert r.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# 5c. Publish + Update
# ══════════════════════════════════════════════════════════════════════════════

class TestSyllabusPublishUpdate:

    def test_teacher_can_publish_own_syllabus(self, client):
        _override(teacher)
        syllabus = _make_syllabus(status=SyllabusStatusEnum.DRAFT)
        course = _make_course(teacher_id=str(teacher.id))
        with patch("app.repositories.SyllabusRepository.get_by_id",
                   new_callable=AsyncMock, return_value=syllabus), \
             patch("app.repositories.CourseRepository.get_by_id",
                   new_callable=AsyncMock, return_value=course):
            r = client.put("/api/syllabus/syll_001/publish")
        _clear()
        assert r.status_code == 200
        syllabus.set.assert_called_once()
        update_arg = syllabus.set.call_args[0][0]
        assert update_arg["status"] == SyllabusStatusEnum.PUBLISHED

    def test_student_cannot_publish_syllabus(self, client):
        _override(student)
        r = client.put("/api/syllabus/syll_001/publish")
        _clear()
        assert r.status_code == 403

    def test_teacher_can_update_own_syllabus_topics(self, client):
        _override(teacher)
        syllabus = _make_syllabus(status=SyllabusStatusEnum.DRAFT)
        course = _make_course(teacher_id=str(teacher.id))
        with patch("app.repositories.SyllabusRepository.get_by_id",
                   new_callable=AsyncMock, return_value=syllabus), \
             patch("app.repositories.CourseRepository.get_by_id",
                   new_callable=AsyncMock, return_value=course):
            r = client.put("/api/syllabus/syll_001", json={
                "topics": [{"week_number": 2, "title": "Week 2", "description": "More",
                             "objectives": [], "materials": [], "assignments": [],
                             "teacher_notes": None}]
            })
        _clear()
        assert r.status_code == 200
        syllabus.set.assert_called_once()


# ══════════════════════════════════════════════════════════════════════════════
# 5d. Milestones endpoint
# ══════════════════════════════════════════════════════════════════════════════

class TestMilestones:

    def _get_milestones(self, client, user, syllabus):
        _override(user)
        with patch("app.repositories.SyllabusRepository.get_by_course",
                   new_callable=AsyncMock, return_value=syllabus):
            r = client.get("/api/syllabus/course_abc/milestones")
        _clear()
        return r

    def test_milestones_student_draft_returns_404(self, client):
        syllabus = _make_syllabus(status=SyllabusStatusEnum.DRAFT)
        r = self._get_milestones(client, student, syllabus)
        assert r.status_code == 404

    def test_milestones_student_published_returns_200(self, client):
        syllabus = _make_syllabus(status=SyllabusStatusEnum.PUBLISHED)
        r = self._get_milestones(client, student, syllabus)
        assert r.status_code == 200
        body = r.json()
        assert "milestones" in body

    def test_milestones_student_has_no_teacher_notes(self, client):
        syllabus = _make_syllabus(status=SyllabusStatusEnum.PUBLISHED)
        r = self._get_milestones(client, student, syllabus)
        assert r.status_code == 200
        milestones = r.json()["milestones"]
        assert len(milestones) > 0
        assert milestones[0].get("teacher_notes") is None

    def test_milestones_teacher_sees_teacher_notes(self, client):
        syllabus = _make_syllabus(status=SyllabusStatusEnum.DRAFT)
        r = self._get_milestones(client, teacher, syllabus)
        assert r.status_code == 200
        milestones = r.json()["milestones"]
        assert milestones[0]["teacher_notes"] == "Private note for teacher only."
