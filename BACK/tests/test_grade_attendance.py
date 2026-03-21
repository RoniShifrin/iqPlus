"""
Tests: Grade Updates, Attendance, Progress Score Recalculation, and Integration.
Covers requirements:
  3. Grade update workflow (RBAC, persistence, validation)
  4. Progress score recalculation after every academic update
  5. Attendance + Feedback + Grade integration scenario
  9. API response codes
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime

from app.main import app
from app.security import get_current_user, get_teacher_user
from app.models import (
    User, Course, Grade, Attendance,
    RoleEnum, AttendanceStatusEnum,
)
from app.services import InsightService


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _make_user(role: RoleEnum, uid: str = None) -> User:
    u = MagicMock(spec=User)
    u.id = uid or f"id_{role.value}"
    u.email = f"{role.value}@test.com"
    u.firebase_uid = u.email
    u.role = role
    u.is_active = True
    u.deleted_at = None
    u.linked_student_ids = []
    u.full_name = MagicMock(return_value=f"{role.value.title()} User")
    return u


def _make_course(teacher_id: str, course_id: str = "course_123") -> Course:
    c = MagicMock(spec=Course)
    c.id = course_id
    c.name = "Math Fundamentals"
    c.teacher_id = teacher_id
    c.deleted_at = None
    return c


def _make_grade(student_id: str = "student_id",
                course_id: str = "course_123",
                score: float = 85.0) -> Grade:
    g = MagicMock(spec=Grade)
    g.id = "grade_xyz"
    g.student_id = student_id
    g.course_id  = course_id
    g.score      = score
    g.subject    = "Algebra"
    g.recorded_at = datetime.utcnow()
    return g


def _make_attendance(student_id: str = "student_id",
                     course_id: str = "course_123",
                     status: str = "present") -> Attendance:
    a = MagicMock(spec=Attendance)
    a.id         = "att_xyz"
    a.student_id = student_id
    a.course_id  = course_id
    a.date       = datetime.utcnow()
    a.status     = AttendanceStatusEnum.PRESENT
    a.remarks    = None
    return a


def _override(user: User):
    async def _dep():
        return user
    app.dependency_overrides[get_current_user] = _dep


def _clear():
    app.dependency_overrides.clear()


# Shared actor users
admin         = _make_user(RoleEnum.ADMIN,   "admin_id")
teacher       = _make_user(RoleEnum.TEACHER, "teacher_id")
other_teacher = _make_user(RoleEnum.TEACHER, "other_id")
student       = _make_user(RoleEnum.STUDENT, "student_id")
parent        = _make_user(RoleEnum.PARENT,  "parent_id")

GRADE_PAYLOAD = {
    "student_id": "student_id",
    "course_id":  "course_123",
    "score":      85.0,
    "subject":    "Algebra",
}

ATTENDANCE_PAYLOAD = {
    "student_id": "student_id",
    "course_id":  "course_123",
    "date":       "2025-04-21T09:00:00",
    "status":     "present",
}


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


# ══════════════════════════════════════════════════════════════════════════════
# 3a. GRADE RBAC TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestGradeRBAC:
    def _post_grade(self, client, user, payload=None, course=None):
        _override(user)
        _course = course or _make_course(str(teacher.id))
        grade   = _make_grade()

        with patch("app.repositories.CourseRepository.get_by_id",
                   new_callable=AsyncMock, return_value=_course), \
             patch("app.repositories.GradeRepository.create",
                   new_callable=AsyncMock, return_value=grade), \
             patch.object(InsightService, "check_and_generate_insights",
                          new_callable=AsyncMock, return_value=None), \
             patch("app.services.score_service.compute_and_save",
                   new_callable=AsyncMock, return_value=None):
            r = client.post("/api/academic/grades", json=payload or GRADE_PAYLOAD)
        _clear()
        return r

    def test_teacher_can_record_grade_for_own_course(self, client):
        r = self._post_grade(client, teacher)
        assert r.status_code == 201

    def test_other_teacher_cannot_record_grade(self, client):
        """other_teacher does not own course_123."""
        _override(other_teacher)
        course = _make_course(str(teacher.id))  # owned by teacher
        with patch("app.repositories.CourseRepository.get_by_id",
                   new_callable=AsyncMock, return_value=course):
            r = client.post("/api/academic/grades", json=GRADE_PAYLOAD)
        _clear()
        assert r.status_code == 403

    def test_student_cannot_record_grade(self, client):
        """Students don't have teacher access — get_teacher_user returns 403."""
        r = self._post_grade(client, student)
        assert r.status_code == 403

    def test_parent_cannot_record_grade(self, client):
        r = self._post_grade(client, parent)
        assert r.status_code == 403

    def test_admin_can_record_grade_for_any_course(self, client):
        r = self._post_grade(client, admin)
        assert r.status_code == 201

    def test_unauthenticated_request_returns_401(self, client):
        r = client.post("/api/academic/grades", json=GRADE_PAYLOAD)
        assert r.status_code == 401

    def test_grade_response_has_correct_student_and_score(self, client):
        r = self._post_grade(client, teacher)
        assert r.status_code == 201
        data = r.json()
        assert data["student_id"] == GRADE_PAYLOAD["student_id"]
        assert data["score"] == GRADE_PAYLOAD["score"]


# ══════════════════════════════════════════════════════════════════════════════
# 3b. GRADE VALIDATION
# ══════════════════════════════════════════════════════════════════════════════

class TestGradeValidation:
    def test_score_above_100_is_rejected(self, client):
        _override(teacher)
        payload = {**GRADE_PAYLOAD, "score": 105.0}
        with patch("app.repositories.CourseRepository.get_by_id",
                   new_callable=AsyncMock, return_value=_make_course(str(teacher.id))):
            r = client.post("/api/academic/grades", json=payload)
        _clear()
        assert r.status_code == 422

    def test_score_below_0_is_rejected(self, client):
        _override(teacher)
        payload = {**GRADE_PAYLOAD, "score": -5.0}
        with patch("app.repositories.CourseRepository.get_by_id",
                   new_callable=AsyncMock, return_value=_make_course(str(teacher.id))):
            r = client.post("/api/academic/grades", json=payload)
        _clear()
        assert r.status_code == 422

    def test_missing_subject_returns_422(self, client):
        _override(teacher)
        payload = {k: v for k, v in GRADE_PAYLOAD.items() if k != "subject"}
        with patch("app.repositories.CourseRepository.get_by_id",
                   new_callable=AsyncMock, return_value=_make_course(str(teacher.id))):
            r = client.post("/api/academic/grades", json=payload)
        _clear()
        assert r.status_code == 422

    def test_boundary_score_0_is_accepted(self, client):
        _override(teacher)
        grade = _make_grade(score=0.0)
        with patch("app.repositories.CourseRepository.get_by_id",
                   new_callable=AsyncMock, return_value=_make_course(str(teacher.id))), \
             patch("app.repositories.GradeRepository.create",
                   new_callable=AsyncMock, return_value=grade), \
             patch.object(InsightService, "check_and_generate_insights",
                          new_callable=AsyncMock, return_value=None), \
             patch("app.services.score_service.compute_and_save",
                   new_callable=AsyncMock, return_value=None):
            r = client.post("/api/academic/grades",
                            json={**GRADE_PAYLOAD, "score": 0.0})
        _clear()
        assert r.status_code == 201

    def test_boundary_score_100_is_accepted(self, client):
        _override(teacher)
        grade = _make_grade(score=100.0)
        with patch("app.repositories.CourseRepository.get_by_id",
                   new_callable=AsyncMock, return_value=_make_course(str(teacher.id))), \
             patch("app.repositories.GradeRepository.create",
                   new_callable=AsyncMock, return_value=grade), \
             patch.object(InsightService, "check_and_generate_insights",
                          new_callable=AsyncMock, return_value=None), \
             patch("app.services.score_service.compute_and_save",
                   new_callable=AsyncMock, return_value=None):
            r = client.post("/api/academic/grades",
                            json={**GRADE_PAYLOAD, "score": 100.0})
        _clear()
        assert r.status_code == 201


# ══════════════════════════════════════════════════════════════════════════════
# 3c. ATTENDANCE RBAC
# ══════════════════════════════════════════════════════════════════════════════

class TestAttendanceRBAC:
    def _post_attendance(self, client, user, payload=None, course=None):
        _override(user)
        _course = course or _make_course(str(teacher.id))
        att     = _make_attendance()

        with patch("app.repositories.CourseRepository.get_by_id",
                   new_callable=AsyncMock, return_value=_course), \
             patch("app.repositories.AttendanceRepository.find_by_student_course_date",
                   new_callable=AsyncMock, return_value=None), \
             patch("app.repositories.AttendanceRepository.create",
                   new_callable=AsyncMock, return_value=att), \
             patch.object(InsightService, "check_attendance_insights",
                          new_callable=AsyncMock, return_value=None), \
             patch("app.services.score_service.compute_and_save",
                   new_callable=AsyncMock, return_value=None):
            r = client.post("/api/academic/attendance",
                            json=payload or ATTENDANCE_PAYLOAD)
        _clear()
        return r

    def test_teacher_can_record_attendance(self, client):
        assert self._post_attendance(client, teacher).status_code == 201

    def test_admin_can_record_attendance(self, client):
        assert self._post_attendance(client, admin).status_code == 201

    def test_student_cannot_record_attendance(self, client):
        assert self._post_attendance(client, student).status_code == 403

    def test_parent_cannot_record_attendance(self, client):
        assert self._post_attendance(client, parent).status_code == 403

    def test_other_teacher_cannot_record_attendance_for_others_course(self, client):
        _override(other_teacher)
        course = _make_course(str(teacher.id))
        with patch("app.repositories.CourseRepository.get_by_id",
                   new_callable=AsyncMock, return_value=course):
            r = client.post("/api/academic/attendance", json=ATTENDANCE_PAYLOAD)
        _clear()
        assert r.status_code == 403

    def test_invalid_attendance_status_returns_422(self, client):
        _override(teacher)
        payload = {**ATTENDANCE_PAYLOAD, "status": "maybe"}
        with patch("app.repositories.CourseRepository.get_by_id",
                   new_callable=AsyncMock, return_value=_make_course(str(teacher.id))):
            r = client.post("/api/academic/attendance", json=payload)
        _clear()
        assert r.status_code == 422


# ══════════════════════════════════════════════════════════════════════════════
# 4. SCORE RECALCULATION TRIGGERS
# ══════════════════════════════════════════════════════════════════════════════

class TestScoreRecalculation:
    def test_score_recalculated_after_grade_submission(self, client):
        """compute_and_save must be called with correct ids after grade creation."""
        _override(teacher)
        course     = _make_course(str(teacher.id))
        grade      = _make_grade()
        score_mock = AsyncMock(return_value=None)

        with patch("app.repositories.CourseRepository.get_by_id",
                   new_callable=AsyncMock, return_value=course), \
             patch("app.repositories.GradeRepository.create",
                   new_callable=AsyncMock, return_value=grade), \
             patch.object(InsightService, "check_and_generate_insights",
                          new_callable=AsyncMock, return_value=None), \
             patch("app.services.score_service.compute_and_save", score_mock):
            client.post("/api/academic/grades", json=GRADE_PAYLOAD)
        _clear()
        score_mock.assert_called_once_with("student_id", "course_123")

    def test_score_recalculated_after_attendance_submission(self, client):
        """compute_and_save must be called with correct ids after attendance creation."""
        _override(teacher)
        course     = _make_course(str(teacher.id))
        att        = _make_attendance()
        score_mock = AsyncMock(return_value=None)

        with patch("app.repositories.CourseRepository.get_by_id",
                   new_callable=AsyncMock, return_value=course), \
             patch("app.repositories.AttendanceRepository.find_by_student_course_date",
                   new_callable=AsyncMock, return_value=None), \
             patch("app.repositories.AttendanceRepository.create",
                   new_callable=AsyncMock, return_value=att), \
             patch.object(InsightService, "check_attendance_insights",
                          new_callable=AsyncMock, return_value=None), \
             patch("app.services.score_service.compute_and_save", score_mock):
            client.post("/api/academic/attendance", json=ATTENDANCE_PAYLOAD)
        _clear()
        score_mock.assert_called_once_with("student_id", "course_123")

    def test_insight_check_called_after_grade_submission(self, client):
        """InsightService.check_and_generate_insights must fire after new grade."""
        _override(teacher)
        course         = _make_course(str(teacher.id))
        grade          = _make_grade()
        insight_mock   = AsyncMock(return_value=None)

        with patch("app.repositories.CourseRepository.get_by_id",
                   new_callable=AsyncMock, return_value=course), \
             patch("app.repositories.GradeRepository.create",
                   new_callable=AsyncMock, return_value=grade), \
             patch.object(InsightService, "check_and_generate_insights",
                          insight_mock), \
             patch("app.services.score_service.compute_and_save",
                   new_callable=AsyncMock, return_value=None):
            client.post("/api/academic/grades", json=GRADE_PAYLOAD)
        _clear()
        insight_mock.assert_called_once_with("student_id", "course_123")

    def test_attendance_insight_check_called_after_attendance_submission(self, client):
        """InsightService.check_attendance_insights must fire after new attendance."""
        _override(teacher)
        course        = _make_course(str(teacher.id))
        att           = _make_attendance()
        att_insight   = AsyncMock(return_value=None)

        with patch("app.repositories.CourseRepository.get_by_id",
                   new_callable=AsyncMock, return_value=course), \
             patch("app.repositories.AttendanceRepository.find_by_student_course_date",
                   new_callable=AsyncMock, return_value=None), \
             patch("app.repositories.AttendanceRepository.create",
                   new_callable=AsyncMock, return_value=att), \
             patch.object(InsightService, "check_attendance_insights", att_insight), \
             patch("app.services.score_service.compute_and_save",
                   new_callable=AsyncMock, return_value=None):
            client.post("/api/academic/attendance", json=ATTENDANCE_PAYLOAD)
        _clear()
        att_insight.assert_called_once_with("student_id", "course_123")


# ══════════════════════════════════════════════════════════════════════════════
# 5. INTEGRATION: Attendance → Feedback → Grade pipeline
# ══════════════════════════════════════════════════════════════════════════════

class TestIntegrationWorkflow:
    """
    Scenario: teacher marks attendance, submits feedback, records a grade.
    All three actions should succeed, and each should trigger score recalculation.
    """

    def test_full_academic_cycle_succeeds(self, client):
        _override(teacher)
        course   = _make_course(str(teacher.id))
        grade    = _make_grade()
        att      = _make_attendance()
        feedback_mock = MagicMock(spec=__import__('app.models', fromlist=['Feedback']).Feedback)
        feedback_mock.id            = "fb_1"
        feedback_mock.student_id    = "student_id"
        feedback_mock.course_id     = "course_123"
        feedback_mock.sentiment     = __import__('app.models', fromlist=['SentimentEnum']).SentimentEnum.POSITIVE
        feedback_mock.content       = "Doing well in the integration test."
        feedback_mock.visibility    = __import__('app.models', fromlist=['FeedbackVisibilityEnum']).FeedbackVisibilityEnum.PRIVATE
        feedback_mock.delivery_target = __import__('app.models', fromlist=['FeedbackDeliveryEnum']).FeedbackDeliveryEnum.NONE
        feedback_mock.email_delivered = False
        feedback_mock.submitted_at  = datetime.utcnow()
        feedback_mock.set           = AsyncMock(return_value=None)

        score_calls = []
        async def _track_score(sid, cid):
            score_calls.append((sid, cid))

        with patch("app.repositories.CourseRepository.get_by_id",
                   new_callable=AsyncMock, return_value=course), \
             patch("app.repositories.GradeRepository.create",
                   new_callable=AsyncMock, return_value=grade), \
             patch("app.repositories.AttendanceRepository.find_by_student_course_date",
                   new_callable=AsyncMock, return_value=None), \
             patch("app.repositories.AttendanceRepository.create",
                   new_callable=AsyncMock, return_value=att), \
             patch("app.repositories.EnrollmentRepository.get_by_student_course",
                   new_callable=AsyncMock, return_value=MagicMock(status=__import__('app.models', fromlist=['EnrollmentStatusEnum']).EnrollmentStatusEnum.ACTIVE)), \
             patch("app.repositories.FeedbackRepository.create",
                   new_callable=AsyncMock, return_value=feedback_mock), \
             patch.object(InsightService, "check_and_generate_insights",
                          new_callable=AsyncMock, return_value=None), \
             patch.object(InsightService, "check_attendance_insights",
                          new_callable=AsyncMock, return_value=None), \
             patch.object(InsightService, "check_feedback_pattern",
                          new_callable=AsyncMock, return_value=None), \
             patch("app.api.routes.academic._deliver_feedback_email",
                   new_callable=AsyncMock, return_value=None), \
             patch("app.repositories.NotificationRepository.create",
                   new_callable=AsyncMock, return_value=None), \
             patch("app.services.score_service.compute_and_save", side_effect=_track_score):

            r_att = client.post("/api/academic/attendance", json=ATTENDANCE_PAYLOAD)
            r_fb  = client.post("/api/academic/feedback",
                                json={"student_id": "student_id", "course_id": "course_123",
                                      "sentiment": "positive",
                                      "content": "Doing well in the integration test.",
                                      "visibility": "private", "delivery_target": "none"})
            r_gr  = client.post("/api/academic/grades", json=GRADE_PAYLOAD)

        _clear()
        assert r_att.status_code == 201, f"Attendance failed: {r_att.json()}"
        assert r_fb.status_code  == 201, f"Feedback failed:  {r_fb.json()}"
        assert r_gr.status_code  == 201, f"Grade failed:     {r_gr.json()}"
        # Score recomputed exactly three times — once per action
        assert len(score_calls) == 3
        for sid, cid in score_calls:
            assert sid == "student_id"
            assert cid == "course_123"

    def test_no_conflicting_writes_same_student_course(self, client):
        """Multiple calls to compute_and_save for the same (student, course) are safe."""
        _override(teacher)
        course = _make_course(str(teacher.id))
        grade  = _make_grade()
        score_mock = AsyncMock(return_value=None)

        with patch("app.repositories.CourseRepository.get_by_id",
                   new_callable=AsyncMock, return_value=course), \
             patch("app.repositories.GradeRepository.create",
                   new_callable=AsyncMock, return_value=grade), \
             patch.object(InsightService, "check_and_generate_insights",
                          new_callable=AsyncMock, return_value=None), \
             patch("app.services.score_service.compute_and_save", score_mock):
            # Submit two grades in sequence — both should succeed
            r1 = client.post("/api/academic/grades", json=GRADE_PAYLOAD)
            r2 = client.post("/api/academic/grades",
                             json={**GRADE_PAYLOAD, "score": 78.0})
        _clear()
        assert r1.status_code == 201
        assert r2.status_code == 201
        assert score_mock.call_count == 2

    def test_score_classification_boundaries_at_service_level(self):
        """Unit test: _classify function maps scores to correct categories."""
        from app.services.score_service import _classify
        from app.models import ScoreClassificationEnum

        assert _classify(80.0) == ScoreClassificationEnum.EXCELLENT
        assert _classify(95.0) == ScoreClassificationEnum.EXCELLENT
        assert _classify(65.0) == ScoreClassificationEnum.GOOD
        assert _classify(79.9) == ScoreClassificationEnum.GOOD
        assert _classify(50.0) == ScoreClassificationEnum.AVERAGE
        assert _classify(64.9) == ScoreClassificationEnum.AVERAGE
        assert _classify(49.9) == ScoreClassificationEnum.NEEDS_ATTENTION
        assert _classify(0.0)  == ScoreClassificationEnum.NEEDS_ATTENTION
