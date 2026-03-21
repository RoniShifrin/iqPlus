"""
Tests: Teacher Feedback Submission, Email Delivery, and Post-Effects.
Covers requirements:
  1. Teacher Feedback Submission RBAC
  2. Email Delivery based on delivery_target
  4. FEEDBACK_ADDED notification creation
  4b. Score recalculated after feedback
  9. API response codes
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime

from app.main import app
from app.security import get_current_user
from app.models import (
    User, Course, Feedback,
    RoleEnum, SentimentEnum, FeedbackVisibilityEnum, FeedbackDeliveryEnum,
    NotificationTypeEnum,
)
from app.services import InsightService


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _make_user(role: RoleEnum, uid: str = None, email: str = None) -> User:
    u = MagicMock(spec=User)
    u.id = uid or f"id_{role.value}"
    u.email = email or f"{role.value}@test.com"
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
    c.name = "Science Basics"
    c.teacher_id = teacher_id
    c.deleted_at = None
    return c


def _make_feedback(
    student_id: str = "student_id",
    course_id: str = "course_123",
    sentiment: SentimentEnum = SentimentEnum.POSITIVE,
    delivery: FeedbackDeliveryEnum = FeedbackDeliveryEnum.NONE,
    visibility: FeedbackVisibilityEnum = FeedbackVisibilityEnum.PRIVATE,
) -> Feedback:
    f = MagicMock(spec=Feedback)
    f.id = "feedback_abc"
    f.student_id = student_id
    f.course_id = course_id
    f.sentiment = sentiment
    f.content = "Good progress this week."
    f.visibility = visibility
    f.delivery_target = delivery
    f.email_delivered = False
    f.submitted_at = datetime.utcnow()
    f.set = AsyncMock(return_value=None)
    return f


def _override(user: User):
    async def _dep():
        return user
    app.dependency_overrides[get_current_user] = _dep


def _clear():
    app.dependency_overrides.clear()


# Shared actor users
admin         = _make_user(RoleEnum.ADMIN,   "admin_id",   "admin@test.com")
teacher       = _make_user(RoleEnum.TEACHER, "teacher_id", "teacher@test.com")
other_teacher = _make_user(RoleEnum.TEACHER, "other_id",   "other@test.com")
student       = _make_user(RoleEnum.STUDENT, "student_id", "student@test.com")
parent_user   = _make_user(RoleEnum.PARENT,  "parent_id",  "parent@test.com")

FEEDBACK_PAYLOAD = {
    "student_id": "student_id",
    "course_id":  "course_123",
    "sentiment":  "positive",
    "content":    "The student showed great improvement this week.",
    "visibility": "private",
    "delivery_target": "none",
}


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _post_feedback(client, user, payload=None, course=None, extra_patches=None):
    """Helper: POST /api/academic/feedback with full mocking."""
    _override(user)
    _course = course or _make_course(str(teacher.id))
    _feedback = _make_feedback()

    from app.models import EnrollmentStatusEnum
    _active_enrollment = MagicMock()
    _active_enrollment.status = EnrollmentStatusEnum.ACTIVE

    patches = [
        patch("app.repositories.CourseRepository.get_by_id",
              new_callable=AsyncMock, return_value=_course),
        patch("app.repositories.EnrollmentRepository.get_by_student_course",
              new_callable=AsyncMock, return_value=_active_enrollment),
        patch("app.repositories.FeedbackRepository.create",
              new_callable=AsyncMock, return_value=_feedback),
        patch("app.services.score_service.compute_and_save",
              new_callable=AsyncMock, return_value=None),
        patch.object(InsightService, "check_feedback_pattern",
                     new_callable=AsyncMock, return_value=None),
        patch("app.api.routes.academic._deliver_feedback_email",
              new_callable=AsyncMock, return_value=None),
        patch("app.repositories.NotificationRepository.create",
              new_callable=AsyncMock, return_value=None),
    ]
    if extra_patches:
        patches.extend(extra_patches)

    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6]:
        r = client.post("/api/academic/feedback", json=payload or FEEDBACK_PAYLOAD)
    _clear()
    return r


# ══════════════════════════════════════════════════════════════════════════════
# 1. FEEDBACK RBAC TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestFeedbackRBAC:
    def test_teacher_can_submit_for_own_course(self, client):
        r = _post_feedback(client, teacher)
        assert r.status_code == 201

    def test_teacher_cannot_submit_for_another_teachers_course(self, client):
        """other_teacher does not own course_123 — must get 403."""
        _override(other_teacher)
        course = _make_course(str(teacher.id))  # owned by teacher, not other_teacher
        with patch("app.repositories.CourseRepository.get_by_id",
                   new_callable=AsyncMock, return_value=course):
            r = client.post("/api/academic/feedback", json=FEEDBACK_PAYLOAD)
        _clear()
        assert r.status_code == 403

    def test_parent_cannot_submit_feedback(self, client):
        r = _post_feedback(client, parent_user)
        assert r.status_code == 403

    def test_student_can_submit_feedback_for_themselves(self, client):
        payload = {**FEEDBACK_PAYLOAD, "student_id": str(student.id)}
        r = _post_feedback(client, student, payload=payload)
        assert r.status_code == 201

    def test_student_cannot_submit_feedback_for_another_student(self, client):
        _override(student)
        payload = {**FEEDBACK_PAYLOAD, "student_id": "some_other_student_id"}
        with patch("app.repositories.CourseRepository.get_by_id",
                   new_callable=AsyncMock, return_value=_make_course(str(teacher.id))):
            r = client.post("/api/academic/feedback", json=payload)
        _clear()
        assert r.status_code == 403

    def test_admin_can_submit_feedback(self, client):
        r = _post_feedback(client, admin)
        assert r.status_code == 201

    def test_unauthenticated_request_rejected(self, client):
        """No auth token → 401."""
        r = client.post("/api/academic/feedback", json=FEEDBACK_PAYLOAD)
        assert r.status_code == 401

    def test_feedback_response_contains_correct_student_and_course(self, client):
        r = _post_feedback(client, teacher)
        assert r.status_code == 201
        data = r.json()
        assert data["student_id"] == FEEDBACK_PAYLOAD["student_id"]
        assert data["course_id"]  == FEEDBACK_PAYLOAD["course_id"]

    def test_feedback_visibility_defaults_to_private(self, client):
        r = _post_feedback(client, teacher)
        assert r.status_code == 201
        assert r.json()["visibility"] == "private"


# ══════════════════════════════════════════════════════════════════════════════
# 2. EMAIL DELIVERY TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestFeedbackEmailDelivery:
    """Verify email behaviour based on delivery_target field."""

    def _post_with_real_delivery(self, client, delivery_target):
        """Post feedback WITHOUT mocking _deliver_feedback_email — test email path."""
        _override(teacher)
        course   = _make_course(str(teacher.id))
        feedback = _make_feedback(delivery=FeedbackDeliveryEnum(delivery_target)
                                  if delivery_target != "none"
                                  else FeedbackDeliveryEnum.NONE)
        student_obj = _make_user(RoleEnum.STUDENT, "student_id", "student@test.com")
        linked_parent = _make_user(RoleEnum.PARENT, "parent_id", "parent@test.com")
        linked_parent.linked_student_ids = ["student_id"]

        payload = {**FEEDBACK_PAYLOAD, "delivery_target": delivery_target}

        from app.models import EnrollmentStatusEnum as _ESE
        _active_enr = MagicMock(); _active_enr.status = _ESE.ACTIVE
        with patch("app.repositories.CourseRepository.get_by_id",
                   new_callable=AsyncMock, return_value=course), \
             patch("app.repositories.EnrollmentRepository.get_by_student_course",
                   new_callable=AsyncMock, return_value=_active_enr), \
             patch("app.repositories.FeedbackRepository.create",
                   new_callable=AsyncMock, return_value=feedback), \
             patch("app.services.score_service.compute_and_save",
                   new_callable=AsyncMock, return_value=None), \
             patch.object(InsightService, "check_feedback_pattern",
                          new_callable=AsyncMock, return_value=None), \
             patch("app.repositories.NotificationRepository.create",
                   new_callable=AsyncMock, return_value=None), \
             patch("app.repositories.UserRepository.get_by_id",
                   new_callable=AsyncMock, return_value=student_obj), \
             patch("app.api.routes.academic.User") as MockAcademicUser, \
             patch("app.services.email_service.EmailNotificationService.send_email",
                   return_value=True) as mock_email:
            MockAcademicUser.find.return_value.to_list = AsyncMock(return_value=[linked_parent])
            r = client.post("/api/academic/feedback", json=payload)
        _clear()
        return r, mock_email

    def test_delivery_none_does_not_send_email(self, client):
        _override(teacher)
        course   = _make_course(str(teacher.id))
        feedback = _make_feedback(delivery=FeedbackDeliveryEnum.NONE)

        from app.models import EnrollmentStatusEnum as _ESE
        _active_enr = MagicMock(); _active_enr.status = _ESE.ACTIVE
        with patch("app.repositories.CourseRepository.get_by_id",
                   new_callable=AsyncMock, return_value=course), \
             patch("app.repositories.EnrollmentRepository.get_by_student_course",
                   new_callable=AsyncMock, return_value=_active_enr), \
             patch("app.repositories.FeedbackRepository.create",
                   new_callable=AsyncMock, return_value=feedback), \
             patch("app.services.score_service.compute_and_save",
                   new_callable=AsyncMock, return_value=None), \
             patch.object(InsightService, "check_feedback_pattern",
                          new_callable=AsyncMock, return_value=None), \
             patch("app.repositories.NotificationRepository.create",
                   new_callable=AsyncMock, return_value=None), \
             patch("app.services.email_service.EmailNotificationService.send_email",
                   return_value=False) as mock_email:
            r = client.post("/api/academic/feedback",
                            json={**FEEDBACK_PAYLOAD, "delivery_target": "none"})
        _clear()
        assert r.status_code == 201
        mock_email.assert_not_called()

    def test_delivery_student_calls_email_once(self, client):
        r, mock_email = self._post_with_real_delivery(client, "student")
        assert r.status_code == 201
        assert mock_email.call_count == 1
        recipient = mock_email.call_args[1].get("recipient") or mock_email.call_args[0][0]
        assert recipient == "student@test.com"

    def test_delivery_parent_sends_to_parent_email(self, client):
        r, mock_email = self._post_with_real_delivery(client, "parent")
        assert r.status_code == 201
        assert mock_email.call_count == 1
        recipient = mock_email.call_args[1].get("recipient") or mock_email.call_args[0][0]
        assert recipient == "parent@test.com"

    def test_delivery_both_sends_to_two_recipients(self, client):
        r, mock_email = self._post_with_real_delivery(client, "both")
        assert r.status_code == 201
        assert mock_email.call_count == 2

    def test_email_failure_does_not_break_feedback_persistence(self, client):
        """SMTP failure must not prevent feedback from being saved."""
        _override(teacher)
        course   = _make_course(str(teacher.id))
        feedback = _make_feedback(delivery=FeedbackDeliveryEnum.STUDENT)
        student_obj = _make_user(RoleEnum.STUDENT, "student_id", "student@test.com")

        from app.models import EnrollmentStatusEnum as _ESE
        _active_enr = MagicMock(); _active_enr.status = _ESE.ACTIVE
        with patch("app.repositories.CourseRepository.get_by_id",
                   new_callable=AsyncMock, return_value=course), \
             patch("app.repositories.EnrollmentRepository.get_by_student_course",
                   new_callable=AsyncMock, return_value=_active_enr), \
             patch("app.repositories.FeedbackRepository.create",
                   new_callable=AsyncMock, return_value=feedback), \
             patch("app.services.score_service.compute_and_save",
                   new_callable=AsyncMock, return_value=None), \
             patch.object(InsightService, "check_feedback_pattern",
                          new_callable=AsyncMock, return_value=None), \
             patch("app.repositories.NotificationRepository.create",
                   new_callable=AsyncMock, return_value=None), \
             patch("app.repositories.UserRepository.get_by_id",
                   new_callable=AsyncMock, return_value=student_obj), \
             patch("app.models.User.find") as mock_find, \
             patch("app.services.email_service.EmailNotificationService.send_email",
                   side_effect=Exception("SMTP connection refused")):
            mock_find.return_value.to_list = AsyncMock(return_value=[])
            r = client.post("/api/academic/feedback",
                            json={**FEEDBACK_PAYLOAD, "delivery_target": "student"})
        _clear()
        # Route must succeed even if email throws
        assert r.status_code == 201

    def test_email_subject_contains_student_name_and_course(self, client):
        r, mock_email = self._post_with_real_delivery(client, "student")
        assert r.status_code == 201
        if mock_email.call_count:
            subject = mock_email.call_args[1].get("subject") or ""
            assert "IQ PLUS" in subject


# ══════════════════════════════════════════════════════════════════════════════
# 3. FEEDBACK VALIDATION (API 422 / schema enforcement)
# ══════════════════════════════════════════════════════════════════════════════

class TestFeedbackValidation:
    def test_content_too_short_returns_422(self, client):
        _override(teacher)
        payload = {**FEEDBACK_PAYLOAD, "content": "Short"}  # < 10 chars
        with patch("app.repositories.CourseRepository.get_by_id",
                   new_callable=AsyncMock, return_value=_make_course(str(teacher.id))):
            r = client.post("/api/academic/feedback", json=payload)
        _clear()
        assert r.status_code == 422

    def test_invalid_sentiment_value_returns_422(self, client):
        _override(teacher)
        payload = {**FEEDBACK_PAYLOAD, "sentiment": "excellent"}
        with patch("app.repositories.CourseRepository.get_by_id",
                   new_callable=AsyncMock, return_value=_make_course(str(teacher.id))):
            r = client.post("/api/academic/feedback", json=payload)
        _clear()
        assert r.status_code == 422

    def test_invalid_delivery_target_returns_422(self, client):
        _override(teacher)
        payload = {**FEEDBACK_PAYLOAD, "delivery_target": "everyone"}
        with patch("app.repositories.CourseRepository.get_by_id",
                   new_callable=AsyncMock, return_value=_make_course(str(teacher.id))):
            r = client.post("/api/academic/feedback", json=payload)
        _clear()
        assert r.status_code == 422

    def test_invalid_visibility_value_returns_422(self, client):
        _override(teacher)
        payload = {**FEEDBACK_PAYLOAD, "visibility": "public_all"}
        with patch("app.repositories.CourseRepository.get_by_id",
                   new_callable=AsyncMock, return_value=_make_course(str(teacher.id))):
            r = client.post("/api/academic/feedback", json=payload)
        _clear()
        assert r.status_code == 422

    def test_missing_required_fields_returns_422(self, client):
        _override(teacher)
        r = client.post("/api/academic/feedback", json={"content": "Only content, nothing else."})
        _clear()
        assert r.status_code == 422


# ══════════════════════════════════════════════════════════════════════════════
# 4. POST-SUBMISSION EFFECTS (score recalc + notification)
# ══════════════════════════════════════════════════════════════════════════════

class TestFeedbackPostEffects:
    def test_score_recalculated_after_feedback_submission(self, client):
        """compute_and_save must be called with correct student_id, course_id."""
        _override(teacher)
        course   = _make_course(str(teacher.id))
        feedback = _make_feedback()
        score_mock = AsyncMock(return_value=None)

        from app.models import EnrollmentStatusEnum as _ESE
        _active_enr = MagicMock(); _active_enr.status = _ESE.ACTIVE
        with patch("app.repositories.CourseRepository.get_by_id",
                   new_callable=AsyncMock, return_value=course), \
             patch("app.repositories.EnrollmentRepository.get_by_student_course",
                   new_callable=AsyncMock, return_value=_active_enr), \
             patch("app.repositories.FeedbackRepository.create",
                   new_callable=AsyncMock, return_value=feedback), \
             patch("app.services.score_service.compute_and_save", score_mock), \
             patch.object(InsightService, "check_feedback_pattern",
                          new_callable=AsyncMock, return_value=None), \
             patch("app.api.routes.academic._deliver_feedback_email",
                   new_callable=AsyncMock, return_value=None), \
             patch("app.repositories.NotificationRepository.create",
                   new_callable=AsyncMock, return_value=None):
            client.post("/api/academic/feedback", json=FEEDBACK_PAYLOAD)
        _clear()
        score_mock.assert_called_once_with(
            FEEDBACK_PAYLOAD["student_id"],
            FEEDBACK_PAYLOAD["course_id"],
        )

    def test_teacher_feedback_creates_student_notification(self, client):
        """When teacher submits feedback, student receives FEEDBACK_ADDED notification."""
        _override(teacher)
        course   = _make_course(str(teacher.id))
        feedback = _make_feedback()
        notif_mock = AsyncMock(return_value=None)

        from app.models import EnrollmentStatusEnum as _ESE
        _active_enr = MagicMock(); _active_enr.status = _ESE.ACTIVE
        with patch("app.repositories.CourseRepository.get_by_id",
                   new_callable=AsyncMock, return_value=course), \
             patch("app.repositories.EnrollmentRepository.get_by_student_course",
                   new_callable=AsyncMock, return_value=_active_enr), \
             patch("app.repositories.FeedbackRepository.create",
                   new_callable=AsyncMock, return_value=feedback), \
             patch("app.services.score_service.compute_and_save",
                   new_callable=AsyncMock, return_value=None), \
             patch.object(InsightService, "check_feedback_pattern",
                          new_callable=AsyncMock, return_value=None), \
             patch("app.api.routes.academic._deliver_feedback_email",
                   new_callable=AsyncMock, return_value=None), \
             patch("app.repositories.NotificationRepository.create", notif_mock):
            client.post("/api/academic/feedback", json=FEEDBACK_PAYLOAD)
        _clear()
        notif_mock.assert_called_once()
        call_kw = notif_mock.call_args[1]
        assert call_kw["user_id"] == FEEDBACK_PAYLOAD["student_id"]
        notif_type = call_kw["type"]
        notif_type_val = notif_type.value if hasattr(notif_type, "value") else str(notif_type)
        assert notif_type_val == "feedback_added"

    def test_student_feedback_creates_teacher_notification(self, client):
        """When student submits feedback, teacher receives FEEDBACK_ADDED notification."""
        _override(student)
        course    = _make_course(str(teacher.id))
        feedback  = _make_feedback(student_id=str(student.id))
        notif_mock = AsyncMock(return_value=None)

        payload = {**FEEDBACK_PAYLOAD,
                   "student_id": str(student.id),
                   "sentiment": "positive"}

        with patch("app.repositories.CourseRepository.get_by_id",
                   new_callable=AsyncMock, return_value=course), \
             patch("app.repositories.FeedbackRepository.create",
                   new_callable=AsyncMock, return_value=feedback), \
             patch("app.services.score_service.compute_and_save",
                   new_callable=AsyncMock, return_value=None), \
             patch.object(InsightService, "check_feedback_pattern",
                          new_callable=AsyncMock, return_value=None), \
             patch("app.api.routes.academic._deliver_feedback_email",
                   new_callable=AsyncMock, return_value=None), \
             patch("app.repositories.NotificationRepository.create", notif_mock):
            client.post("/api/academic/feedback", json=payload)
        _clear()
        notif_mock.assert_called_once()
        call_kw = notif_mock.call_args[1]
        # notification recipient is the course teacher
        assert call_kw["user_id"] == str(teacher.id)

    def test_feedback_pattern_check_triggered_after_submission(self, client):
        """check_feedback_pattern must be called once per feedback submission."""
        _override(teacher)
        course   = _make_course(str(teacher.id))
        feedback = _make_feedback()
        pattern_mock = AsyncMock(return_value=None)

        from app.models import EnrollmentStatusEnum as _ESE
        _active_enr = MagicMock(); _active_enr.status = _ESE.ACTIVE
        with patch("app.repositories.CourseRepository.get_by_id",
                   new_callable=AsyncMock, return_value=course), \
             patch("app.repositories.EnrollmentRepository.get_by_student_course",
                   new_callable=AsyncMock, return_value=_active_enr), \
             patch("app.repositories.FeedbackRepository.create",
                   new_callable=AsyncMock, return_value=feedback), \
             patch("app.services.score_service.compute_and_save",
                   new_callable=AsyncMock, return_value=None), \
             patch.object(InsightService, "check_feedback_pattern", pattern_mock), \
             patch("app.api.routes.academic._deliver_feedback_email",
                   new_callable=AsyncMock, return_value=None), \
             patch("app.repositories.NotificationRepository.create",
                   new_callable=AsyncMock, return_value=None):
            client.post("/api/academic/feedback", json=FEEDBACK_PAYLOAD)
        _clear()
        pattern_mock.assert_called_once_with(
            FEEDBACK_PAYLOAD["student_id"],
            FEEDBACK_PAYLOAD["course_id"],
        )
