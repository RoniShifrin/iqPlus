"""
RBAC tests for Course endpoints.
Uses FastAPI TestClient with dependency overrides — no live DB needed.
Run: cd BACK && pytest tests/ -v
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.main import app
from app.security import get_current_user
from app.models import User, Course, RoleEnum, CourseStatusEnum, VisibilityScopeEnum


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_user(role: RoleEnum, uid: str = None) -> User:
    u = MagicMock(spec=User)
    u.id = uid or f"id_{role.value}"
    u.email = f"{role.value}@test.com"
    u.firebase_uid = u.email
    u.role = role
    u.is_active = True
    u.deleted_at = None
    return u


def _make_course(teacher_id: str,
                 status=CourseStatusEnum.DRAFT,
                 visibility=VisibilityScopeEnum.SCHOOL_ONLY) -> Course:
    c = MagicMock(spec=Course)
    c.id = "course_abc123"
    c.code = "TEST101"
    c.name = "Test Course"
    c.description = "desc"
    c.teacher_id = teacher_id
    c.created_by_role = "teacher"
    c.schedule = None
    c.capacity = 30
    c.status = status
    c.visibility_scope = visibility
    c.deleted_at = None
    c.created_at = datetime.utcnow()
    return c


def _override(user: User):
    async def _dep():
        return user
    app.dependency_overrides[get_current_user] = _dep


def _clear():
    app.dependency_overrides.clear()


# ── Shared users ──────────────────────────────────────────────────────────────

admin    = _make_user(RoleEnum.ADMIN,   "admin_id")
teacher  = _make_user(RoleEnum.TEACHER, "teacher_id")
teacher2 = _make_user(RoleEnum.TEACHER, "teacher2_id")
student  = _make_user(RoleEnum.STUDENT, "student_id")
parent   = _make_user(RoleEnum.PARENT,  "parent_id")


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


# ── CREATE ────────────────────────────────────────────────────────────────────

class TestCreateCourse:
    PAYLOAD = {
        "code": "NEW101",
        "name": "New Course",
        "capacity": 25,
        "visibility_scope": "school_only",
    }

    def _post(self, client, user):
        _override(user)
        with patch("app.repositories.CourseRepository.get_by_code",
                   new_callable=AsyncMock, return_value=None), \
             patch("app.repositories.CourseRepository.create",
                   new_callable=AsyncMock,
                   return_value=_make_course(str(user.id))):
            r = client.post("/api/courses/", json=self.PAYLOAD)
        _clear()
        return r

    def test_teacher_can_create(self, client):
        r = self._post(client, teacher)
        assert r.status_code == 201
        assert r.json()["teacher_id"] == str(teacher.id)

    def test_admin_can_create(self, client):
        """Admin must supply a teacher_id; UserRepository must return a valid teacher."""
        _override(admin)
        with patch("app.repositories.CourseRepository.get_by_code",
                   new_callable=AsyncMock, return_value=None), \
             patch("app.repositories.CourseRepository.create",
                   new_callable=AsyncMock,
                   return_value=_make_course(str(teacher.id))), \
             patch("app.repositories.UserRepository.get_by_id",
                   new_callable=AsyncMock, return_value=teacher):
            r = client.post("/api/courses/", json={**self.PAYLOAD, "teacher_id": str(teacher.id)})
        _clear()
        assert r.status_code == 201

    def test_student_cannot_create(self, client):
        assert self._post(client, student).status_code == 403

    def test_parent_cannot_create(self, client):
        assert self._post(client, parent).status_code == 403

    def test_teacher_id_is_always_set_to_creator(self, client):
        """teacher_id in payload is ignored — always the requesting user."""
        _override(teacher)
        payload = {**self.PAYLOAD, "teacher_id": "hacker_id"}
        with patch("app.repositories.CourseRepository.get_by_code",
                   new_callable=AsyncMock, return_value=None), \
             patch("app.repositories.CourseRepository.create",
                   new_callable=AsyncMock,
                   return_value=_make_course(str(teacher.id))):
            r = client.post("/api/courses/", json=payload)
        _clear()
        assert r.status_code == 201
        assert r.json()["teacher_id"] == str(teacher.id)


# ── UPDATE ────────────────────────────────────────────────────────────────────

class TestUpdateCourse:
    PAYLOAD = {"name": "Updated Name"}

    def _put(self, client, user, course):
        _override(user)
        with patch("app.repositories.CourseRepository.get_by_id",
                   new_callable=AsyncMock, return_value=course), \
             patch("app.repositories.CourseRepository.update",
                   new_callable=AsyncMock, return_value=course):
            r = client.put(f"/api/courses/{course.id}", json=self.PAYLOAD)
        _clear()
        return r

    def test_owner_teacher_can_update(self, client):
        assert self._put(client, teacher, _make_course(str(teacher.id))).status_code == 200

    def test_other_teacher_cannot_update(self, client):
        assert self._put(client, teacher2, _make_course(str(teacher.id))).status_code == 403

    def test_admin_can_update_any(self, client):
        assert self._put(client, admin, _make_course(str(teacher.id))).status_code == 200

    def test_student_cannot_update(self, client):
        assert self._put(client, student, _make_course(str(teacher.id))).status_code == 403

    def test_parent_cannot_update(self, client):
        assert self._put(client, parent, _make_course(str(teacher.id))).status_code == 403


# ── PUBLISH / ARCHIVE ─────────────────────────────────────────────────────────

class TestPublishArchive:
    def _action(self, client, user, action, course):
        _override(user)
        course.set = AsyncMock(return_value=None)
        with patch("app.repositories.CourseRepository.get_by_id",
                   new_callable=AsyncMock, return_value=course):
            r = client.post(f"/api/courses/{course.id}/{action}")
        _clear()
        return r

    def test_owner_can_publish(self, client):
        assert self._action(client, teacher, "publish", _make_course(str(teacher.id))).status_code == 200

    def test_other_teacher_cannot_publish(self, client):
        assert self._action(client, teacher2, "publish", _make_course(str(teacher.id))).status_code == 403

    def test_admin_can_publish_any(self, client):
        assert self._action(client, admin, "publish", _make_course(str(teacher.id))).status_code == 200

    def test_student_cannot_publish(self, client):
        assert self._action(client, student, "publish", _make_course(str(teacher.id))).status_code == 403

    def test_owner_can_archive(self, client):
        c = _make_course(str(teacher.id), status=CourseStatusEnum.PUBLISHED)
        assert self._action(client, teacher, "archive", c).status_code == 200

    def test_archived_course_cannot_be_published(self, client):
        c = _make_course(str(teacher.id), status=CourseStatusEnum.ARCHIVED)
        assert self._action(client, teacher, "publish", c).status_code == 400


# ── DELETE ────────────────────────────────────────────────────────────────────

class TestDeleteCourse:
    def _delete(self, client, user, course):
        _override(user)
        course.set = AsyncMock(return_value=None)
        with patch("app.repositories.CourseRepository.get_by_id",
                   new_callable=AsyncMock, return_value=course):
            r = client.delete(f"/api/courses/{course.id}")
        _clear()
        return r

    def test_owner_can_delete(self, client):
        assert self._delete(client, teacher, _make_course(str(teacher.id))).status_code == 204

    def test_other_teacher_cannot_delete(self, client):
        assert self._delete(client, teacher2, _make_course(str(teacher.id))).status_code == 403

    def test_admin_can_delete_any(self, client):
        assert self._delete(client, admin, _make_course(str(teacher.id))).status_code == 204

    def test_student_cannot_delete(self, client):
        assert self._delete(client, student, _make_course(str(teacher.id))).status_code == 403

    def test_parent_cannot_delete(self, client):
        assert self._delete(client, parent, _make_course(str(teacher.id))).status_code == 403
