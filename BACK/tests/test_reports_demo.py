"""
Tests: Report Export RBAC + Demo Data Safety (Areas 6 + 11)
Covers:
  - Student can export own report; blocked from another student's
  - Admin can export any student report
  - Parent can export linked child; blocked from unlinked
  - Teacher can export report for student enrolled in their course
  - Course report: teacher (own course) 200, teacher (other course) 403, student 403
  - Attendance export: teacher own 200, parent blocked 403
  - Invalid format → 422 (FastAPI query validation)
  - Demo status: admin 200, non-admin 403
  - Demo clear: invalid dataset 400, result contains real_data_safe=True
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch

from app.main import app
from app.security import get_current_user
from app.models import User, RoleEnum


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_user(role: RoleEnum, uid: str = None, linked: list = None) -> User:
    u = MagicMock(spec=User)
    u.id = uid or f"id_{role.value}"
    u.email = f"{role.value}@test.com"
    u.role = role
    u.is_active = True
    u.deleted_at = None
    u.linked_student_ids = linked or []
    u.full_name = MagicMock(return_value=role.value.title())
    return u


def _override(user):
    async def _dep():
        return user
    app.dependency_overrides[get_current_user] = _dep


def _clear():
    app.dependency_overrides.clear()


teacher = _make_user(RoleEnum.TEACHER, "teacher_id")
admin   = _make_user(RoleEnum.ADMIN,   "admin_id")
student = _make_user(RoleEnum.STUDENT, "student_id")
parent  = _make_user(RoleEnum.PARENT,  "parent_id", linked=["student_id"])


FAKE_CONTENT = b"fake,report,data"
FAKE_CSV = (FAKE_CONTENT, "text/csv", "report.csv")


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


# ══════════════════════════════════════════════════════════════════════════════
# 6a. Student report export — RBAC
# ══════════════════════════════════════════════════════════════════════════════

class TestStudentReportExport:

    def _export(self, client, user, sid, fmt="csv"):
        _override(user)
        with patch("app.api.routes.reports.generate_student_report",
                   new_callable=AsyncMock, return_value=FAKE_CSV):
            r = client.get(f"/api/reports/student/{sid}/export?format={fmt}")
        _clear()
        return r

    def test_student_can_export_own_report(self, client):
        r = self._export(client, student, "student_id")
        assert r.status_code == 200
        assert "attachment" in r.headers.get("content-disposition", "")

    def test_student_blocked_from_other_student_report(self, client):
        r = self._export(client, student, "other_student_id")
        assert r.status_code == 403

    def test_admin_can_export_any_student_report(self, client):
        r = self._export(client, admin, "any_student_id")
        assert r.status_code == 200

    def test_parent_can_export_linked_child_report(self, client):
        r = self._export(client, parent, "student_id")  # "student_id" in linked_student_ids
        assert r.status_code == 200

    def test_parent_blocked_from_unlinked_child_report(self, client):
        r = self._export(client, parent, "unlinked_student_id")
        assert r.status_code == 403

    def test_teacher_can_export_enrolled_student_report(self, client):
        _override(teacher)
        enr = MagicMock()
        enr.course_id = "course_abc"
        course = MagicMock()
        course.id = "course_abc"
        with patch("app.repositories.EnrollmentRepository.list_by_student",
                   new_callable=AsyncMock, return_value=[enr]), \
             patch("app.repositories.CourseRepository.list_by_teacher",
                   new_callable=AsyncMock, return_value=[course]), \
             patch("app.api.routes.reports.generate_student_report",
                   new_callable=AsyncMock, return_value=FAKE_CSV):
            r = client.get("/api/reports/student/any_student/export?format=csv")
        _clear()
        assert r.status_code == 200

    def test_teacher_blocked_when_student_not_in_own_courses(self, client):
        _override(teacher)
        enr = MagicMock()
        enr.course_id = "other_course"
        course = MagicMock()
        course.id = "teacher_course"
        with patch("app.repositories.EnrollmentRepository.list_by_student",
                   new_callable=AsyncMock, return_value=[enr]), \
             patch("app.repositories.CourseRepository.list_by_teacher",
                   new_callable=AsyncMock, return_value=[course]):
            r = client.get("/api/reports/student/any_student/export?format=csv")
        _clear()
        assert r.status_code == 403

    def test_invalid_format_returns_422(self, client):
        _override(student)
        r = client.get("/api/reports/student/student_id/export?format=xml")
        _clear()
        assert r.status_code == 422

    def test_report_response_has_content_disposition(self, client):
        _override(admin)
        with patch("app.api.routes.reports.generate_student_report",
                   new_callable=AsyncMock, return_value=FAKE_CSV):
            r = client.get("/api/reports/student/xyz/export?format=csv")
        _clear()
        assert r.status_code == 200
        cd = r.headers.get("content-disposition", "")
        assert "attachment" in cd
        assert "report.csv" in cd


# ══════════════════════════════════════════════════════════════════════════════
# 6b. Course report export — RBAC
# ══════════════════════════════════════════════════════════════════════════════

class TestCourseReportExport:

    def test_teacher_can_export_own_course_report(self, client):
        _override(teacher)
        course = MagicMock()
        course.teacher_id = "teacher_id"
        with patch("app.repositories.CourseRepository.get_by_id",
                   new_callable=AsyncMock, return_value=course), \
             patch("app.api.routes.reports.generate_course_report",
                   new_callable=AsyncMock, return_value=FAKE_CSV):
            r = client.get("/api/reports/course/course_abc/export?format=csv")
        _clear()
        assert r.status_code == 200

    def test_teacher_blocked_from_other_course(self, client):
        _override(teacher)
        course = MagicMock()
        course.teacher_id = "other_teacher_id"
        with patch("app.repositories.CourseRepository.get_by_id",
                   new_callable=AsyncMock, return_value=course):
            r = client.get("/api/reports/course/course_abc/export?format=csv")
        _clear()
        assert r.status_code == 403

    def test_student_blocked_from_course_report(self, client):
        _override(student)
        r = client.get("/api/reports/course/course_abc/export?format=csv")
        _clear()
        assert r.status_code == 403

    def test_admin_can_export_course_report(self, client):
        _override(admin)
        with patch("app.api.routes.reports.generate_course_report",
                   new_callable=AsyncMock, return_value=FAKE_CSV):
            r = client.get("/api/reports/course/any_course/export?format=csv")
        _clear()
        assert r.status_code == 200


# ══════════════════════════════════════════════════════════════════════════════
# 6c. Attendance report export
# ══════════════════════════════════════════════════════════════════════════════

class TestAttendanceReportExport:

    def test_teacher_can_export_attendance_own_course(self, client):
        _override(teacher)
        course = MagicMock()
        course.teacher_id = "teacher_id"
        with patch("app.repositories.CourseRepository.get_by_id",
                   new_callable=AsyncMock, return_value=course), \
             patch("app.api.routes.reports.generate_attendance_report",
                   new_callable=AsyncMock, return_value=FAKE_CSV):
            r = client.get("/api/reports/attendance/course_abc/export?format=csv")
        _clear()
        assert r.status_code == 200

    def test_parent_blocked_from_attendance_export(self, client):
        _override(parent)
        r = client.get("/api/reports/attendance/course_abc/export?format=csv")
        _clear()
        assert r.status_code == 403


# ══════════════════════════════════════════════════════════════════════════════
# 11. Demo data safety
# ══════════════════════════════════════════════════════════════════════════════

def _make_mock_db():
    """Return a mock Motor DB whose collections return empty lists."""
    mock_collection = MagicMock()
    mock_collection.find.return_value.to_list = AsyncMock(return_value=[])
    mock_collection.delete_many = AsyncMock(return_value=MagicMock(deleted_count=0))
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    return mock_db


class TestDemoDataRoutes:

    def _status(self, client, user):
        _override(user)
        mock_client = MagicMock()
        mock_client.__getitem__ = MagicMock(return_value=_make_mock_db())
        with patch("app.api.routes.admin_demo.AsyncIOMotorClient",
                   return_value=mock_client):
            r = client.get("/api/admin/demo/status")
        _clear()
        return r

    def test_admin_can_get_demo_status(self, client):
        r = self._status(client, admin)
        assert r.status_code == 200
        body = r.json()
        assert "small_demo" in body
        assert "large_demo" in body

    def test_teacher_blocked_from_demo_status(self, client):
        r = self._status(client, teacher)
        assert r.status_code == 403

    def test_student_blocked_from_demo_status(self, client):
        r = self._status(client, student)
        assert r.status_code == 403

    def test_demo_clear_invalid_dataset_returns_400(self, client):
        _override(admin)
        mock_client = MagicMock()
        mock_client.__getitem__ = MagicMock(return_value=_make_mock_db())
        with patch("app.api.routes.admin_demo.AsyncIOMotorClient",
                   return_value=mock_client):
            r = client.post("/api/admin/demo/clear?dataset=invalid")
        _clear()
        assert r.status_code == 400

    def test_demo_clear_returns_real_data_safe(self, client):
        _override(admin)
        mock_client = MagicMock()
        mock_client.__getitem__ = MagicMock(return_value=_make_mock_db())
        with patch("app.api.routes.admin_demo.AsyncIOMotorClient",
                   return_value=mock_client):
            r = client.post("/api/admin/demo/clear?dataset=all")
        _clear()
        assert r.status_code == 200
        assert r.json()["real_data_safe"] is True

    def test_demo_clear_small_only(self, client):
        _override(admin)
        mock_client = MagicMock()
        mock_client.__getitem__ = MagicMock(return_value=_make_mock_db())
        with patch("app.api.routes.admin_demo.AsyncIOMotorClient",
                   return_value=mock_client):
            r = client.post("/api/admin/demo/clear?dataset=small")
        _clear()
        assert r.status_code == 200
        body = r.json()
        assert "small_demo" in body["cleared"]
        assert "large_demo" not in body["cleared"]

    def test_demo_clear_non_admin_blocked(self, client):
        _override(teacher)
        r = client.post("/api/admin/demo/clear?dataset=all")
        _clear()
        assert r.status_code == 403

    def test_demo_status_response_structure(self, client):
        _override(admin)
        mock_client = MagicMock()
        mock_client.__getitem__ = MagicMock(return_value=_make_mock_db())
        with patch("app.api.routes.admin_demo.AsyncIOMotorClient",
                   return_value=mock_client):
            r = client.get("/api/admin/demo/status")
        _clear()
        body = r.json()
        assert body["small_demo"]["seeded"] is False
        assert body["large_demo"]["seeded"] is False
        assert "note" in body
