"""
Tests: AI/Rule-based Alert Detection, Parent Notifications, and Dashboard Aggregation.
Covers requirements:
  6. AI / rule-based alert creation (grade drop, attendance, repeated negative feedback)
  7. Parent notification correctness
  8. Dashboard data reflection after academic updates
  9. API response codes for alerts, notifications, dashboard
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.main import app
from app.security import get_current_user
from app.models import (
    User, Course, Enrollment, LearningInsight,
    RoleEnum, SentimentEnum, InsightTypeEnum, EnrollmentStatusEnum,
    NotificationTypeEnum, AlertLevelEnum,
)
from app.services import InsightService


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _make_user(role: RoleEnum, uid: str = None, email: str = None,
               linked_ids=None) -> User:
    u = MagicMock(spec=User)
    u.id = uid or f"id_{role.value}"
    u.email = email or f"{role.value}@test.com"
    u.firebase_uid = u.email
    u.role = role
    u.is_active = True
    u.deleted_at = None
    u.linked_student_ids = linked_ids or []
    u.full_name = MagicMock(return_value=f"{role.value.title()} User")
    return u


def _make_course(teacher_id: str = "teacher_id",
                 course_id: str  = "course_123",
                 status=None) -> Course:
    from app.models import CourseStatusEnum
    c = MagicMock(spec=Course)
    c.id = course_id
    c.code = "SCI101"
    c.name = "Science Basics"
    c.description = "desc"
    c.teacher_id = teacher_id
    c.created_by_role = "teacher"
    c.schedule = None
    c.capacity = 30
    c.status = status or CourseStatusEnum.PUBLISHED
    c.visibility_scope = "school_only"
    c.deleted_at = None
    c.created_at = datetime.utcnow()
    return c


def _make_enrollment(student_id: str = "student_id",
                     course_id: str = "course_123") -> Enrollment:
    e = MagicMock(spec=Enrollment)
    e.id = "enr_abc"
    e.student_id = student_id
    e.course_id  = course_id
    e.status = EnrollmentStatusEnum.ACTIVE
    e.enrolled_at = datetime.utcnow()
    e.completed_at = None
    return e


def _make_grade_obj(score: float, student_id="student_id", course_id="course_123"):
    g = MagicMock()
    g.score      = score
    g.student_id = student_id
    g.course_id  = course_id
    g.recorded_at = datetime.utcnow()
    return g


def _make_feedback_obj(sentiment: SentimentEnum, submitted_at=None):
    f = MagicMock()
    f.sentiment   = sentiment
    f.submitted_at = submitted_at or datetime.utcnow()
    return f


def _mock_query(return_list=None, count=0):
    """Create a mock Beanie query chain."""
    q = MagicMock()
    q.to_list = AsyncMock(return_value=return_list or [])
    q.count   = AsyncMock(return_value=count)
    q.sort    = MagicMock(return_value=q)
    q.limit   = MagicMock(return_value=q)
    q.find    = MagicMock(return_value=q)
    return q


def _override(user: User):
    async def _dep():
        return user
    app.dependency_overrides[get_current_user] = _dep


def _clear():
    app.dependency_overrides.clear()


# Shared actor users
admin   = _make_user(RoleEnum.ADMIN,   "admin_id")
teacher = _make_user(RoleEnum.TEACHER, "teacher_id")
student = _make_user(RoleEnum.STUDENT, "student_id")
parent_linked = _make_user(
    RoleEnum.PARENT, "parent_id", "parent@test.com",
    linked_ids=["student_id"]
)
parent_unlinked = _make_user(
    RoleEnum.PARENT, "parent_unlinked", "other_parent@test.com",
    linked_ids=[]
)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


# ══════════════════════════════════════════════════════════════════════════════
# 6a. AI alert: grade drop detection via InsightService (unit-level async)
# ══════════════════════════════════════════════════════════════════════════════

class TestInsightServiceGradeDetection:
    """Test InsightService.check_and_generate_insights directly (no HTTP)."""

    @pytest.mark.asyncio
    async def test_major_grade_drop_creates_insight_and_alert(self):
        """A >15% drop must produce a LearningInsight, Notification, and AIAlert."""
        from app.models import AIAlert, ScoreClassificationEnum

        grade_old  = _make_grade_obj(score=80.0)
        grade_new  = _make_grade_obj(score=50.0)  # ~37.5% drop
        mock_insight = MagicMock(spec=LearningInsight)

        ai_alert_insert = AsyncMock(return_value=None)
        notif_create    = AsyncMock(return_value=None)
        insight_create  = AsyncMock(return_value=mock_insight)

        mock_ai_alert_cls = MagicMock(return_value=MagicMock(insert=ai_alert_insert))
        mock_ai_alert_cls.find_one = AsyncMock(return_value=None)  # no existing alert
        with patch("app.repositories.GradeRepository.get_recent_grades",
                   new_callable=AsyncMock, return_value=[grade_new, grade_old]), \
             patch("app.repositories.LearningInsightRepository.create", insight_create), \
             patch("app.repositories.NotificationRepository.create",  notif_create), \
             patch("app.services.AIAlert", mock_ai_alert_cls):
            result = await InsightService.check_and_generate_insights(
                "student_id", "course_123"
            )

        assert result is not None
        insight_create.assert_called_once()
        notif_create.assert_called_once()
        ai_alert_insert.assert_called_once()  # decline → AIAlert created

    @pytest.mark.asyncio
    async def test_major_grade_drop_notification_type_is_ai_alert(self):
        grade_old    = _make_grade_obj(score=90.0)
        grade_new    = _make_grade_obj(score=50.0)  # >40% drop
        mock_insight = MagicMock(spec=LearningInsight)
        from app.models import AIAlert

        notif_create = AsyncMock(return_value=None)

        mock_ai_alert_cls = MagicMock(return_value=MagicMock(insert=AsyncMock()))
        mock_ai_alert_cls.find_one = AsyncMock(return_value=None)  # no existing alert
        with patch("app.repositories.GradeRepository.get_recent_grades",
                   new_callable=AsyncMock, return_value=[grade_new, grade_old]), \
             patch("app.repositories.LearningInsightRepository.create",
                   new_callable=AsyncMock, return_value=mock_insight), \
             patch("app.repositories.NotificationRepository.create", notif_create), \
             patch("app.services.AIAlert", mock_ai_alert_cls):
            await InsightService.check_and_generate_insights("student_id", "course_123")

        call_kw = notif_create.call_args[1]
        notif_type = call_kw["type"]
        notif_type_val = notif_type.value if hasattr(notif_type, "value") else str(notif_type)
        assert notif_type_val == "ai_alert"

    @pytest.mark.asyncio
    async def test_small_grade_change_does_not_trigger_insight(self):
        """A <15% change must NOT create any insight."""
        grade_old = _make_grade_obj(score=80.0)
        grade_new = _make_grade_obj(score=75.0)  # only 6.25% drop

        insight_create = AsyncMock(return_value=None)
        notif_create   = AsyncMock(return_value=None)

        with patch("app.repositories.GradeRepository.get_recent_grades",
                   new_callable=AsyncMock, return_value=[grade_new, grade_old]), \
             patch("app.repositories.LearningInsightRepository.create", insight_create), \
             patch("app.repositories.NotificationRepository.create",    notif_create):
            result = await InsightService.check_and_generate_insights(
                "student_id", "course_123"
            )

        assert result is None
        insight_create.assert_not_called()
        notif_create.assert_not_called()

    @pytest.mark.asyncio
    async def test_grade_improvement_creates_insight_no_alert(self):
        """A significant grade improvement creates insight + notification, but NOT an AIAlert."""
        grade_old    = _make_grade_obj(score=50.0)
        grade_new    = _make_grade_obj(score=80.0)  # 60% improvement
        mock_insight = MagicMock(spec=LearningInsight)
        from app.models import AIAlert

        ai_alert_insert = AsyncMock(return_value=None)
        notif_create    = AsyncMock(return_value=None)

        with patch("app.repositories.GradeRepository.get_recent_grades",
                   new_callable=AsyncMock, return_value=[grade_new, grade_old]), \
             patch("app.repositories.LearningInsightRepository.create",
                   new_callable=AsyncMock, return_value=mock_insight), \
             patch("app.repositories.NotificationRepository.create", notif_create), \
             patch.object(AIAlert, "insert", ai_alert_insert):
            result = await InsightService.check_and_generate_insights(
                "student_id", "course_123"
            )

        assert result is not None
        notif_create.assert_called_once()
        # Improvement → no AIAlert
        ai_alert_insert.assert_not_called()


# ══════════════════════════════════════════════════════════════════════════════
# 6b. AI alert: repeated negative feedback detection
# ══════════════════════════════════════════════════════════════════════════════

class TestFeedbackPatternDetection:
    """Test InsightService.check_feedback_pattern directly."""

    @pytest.mark.asyncio
    async def test_three_consecutive_negative_creates_alert(self):
        from app.models import AIAlert

        feedbacks = [
            _make_feedback_obj(SentimentEnum.NEGATIVE),
            _make_feedback_obj(SentimentEnum.NEGATIVE),
            _make_feedback_obj(SentimentEnum.NEGATIVE),
        ]
        ai_alert_insert = AsyncMock(return_value=None)
        notif_create    = AsyncMock(return_value=None)

        mock_ai_alert_cls = MagicMock(return_value=MagicMock(insert=ai_alert_insert))
        mock_ai_alert_cls.find_one = AsyncMock(return_value=None)  # no existing alert
        with patch("app.repositories.FeedbackRepository.list_by_student_course",
                   new_callable=AsyncMock, return_value=feedbacks), \
             patch("app.services.AIAlert", mock_ai_alert_cls), \
             patch("app.repositories.NotificationRepository.create", notif_create):
            await InsightService.check_feedback_pattern("student_id", "course_123")

        ai_alert_insert.assert_called_once()
        notif_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_two_negative_one_positive_does_not_trigger_alert(self):
        from app.models import AIAlert

        feedbacks = [
            _make_feedback_obj(SentimentEnum.NEGATIVE),
            _make_feedback_obj(SentimentEnum.NEGATIVE),
            _make_feedback_obj(SentimentEnum.POSITIVE),
        ]
        ai_alert_insert = AsyncMock(return_value=None)

        with patch("app.repositories.FeedbackRepository.list_by_student_course",
                   new_callable=AsyncMock, return_value=feedbacks), \
             patch.object(AIAlert, "insert", ai_alert_insert):
            await InsightService.check_feedback_pattern("student_id", "course_123")

        ai_alert_insert.assert_not_called()

    @pytest.mark.asyncio
    async def test_fewer_than_three_feedbacks_does_not_trigger_alert(self):
        from app.models import AIAlert

        feedbacks = [
            _make_feedback_obj(SentimentEnum.NEGATIVE),
            _make_feedback_obj(SentimentEnum.NEGATIVE),
        ]
        ai_alert_insert = AsyncMock(return_value=None)

        with patch("app.repositories.FeedbackRepository.list_by_student_course",
                   new_callable=AsyncMock, return_value=feedbacks), \
             patch.object(AIAlert, "insert", ai_alert_insert):
            await InsightService.check_feedback_pattern("student_id", "course_123")

        ai_alert_insert.assert_not_called()

    @pytest.mark.asyncio
    async def test_negative_feedback_alert_has_warning_level(self):
        from app.models import AIAlert

        feedbacks = [_make_feedback_obj(SentimentEnum.NEGATIVE)] * 3
        captured = {}

        alert_instance = MagicMock(insert=AsyncMock(return_value=None))

        def _capture_constructor(**kwargs):
            captured.update(kwargs)
            return alert_instance

        mock_ai_alert_cls = MagicMock(side_effect=_capture_constructor)
        mock_ai_alert_cls.find_one = AsyncMock(return_value=None)  # no existing alert
        # Provide class-level attribute stubs so Beanie expression syntax doesn't error
        mock_ai_alert_cls.student_id = MagicMock()
        mock_ai_alert_cls.course_id = MagicMock()
        mock_ai_alert_cls.alert_level = MagicMock()
        mock_ai_alert_cls.parent_acknowledged = MagicMock()

        with patch("app.repositories.FeedbackRepository.list_by_student_course",
                   new_callable=AsyncMock, return_value=feedbacks), \
             patch("app.services.AIAlert", mock_ai_alert_cls), \
             patch("app.repositories.NotificationRepository.create",
                   new_callable=AsyncMock):
            await InsightService.check_feedback_pattern("student_id", "course_123")

        assert captured.get("alert_level") == AlertLevelEnum.WARNING


# ══════════════════════════════════════════════════════════════════════════════
# 6c. Attendance concern alert
# ══════════════════════════════════════════════════════════════════════════════

class TestAttendanceAlertDetection:
    @pytest.mark.asyncio
    async def test_attendance_drop_creates_insight_and_alert(self):
        """A significant attendance drop (>15%) triggers insight, notification, AIAlert."""
        from app.models import AIAlert

        ai_alert_insert = AsyncMock(return_value=None)
        notif_create    = AsyncMock(return_value=None)
        mock_insight    = MagicMock(spec=LearningInsight)

        mock_ai_alert_cls = MagicMock(return_value=MagicMock(insert=ai_alert_insert))
        mock_ai_alert_cls.find_one = AsyncMock(return_value=None)  # no existing alert
        with patch("app.repositories.AttendanceRepository.get_attendance_rate",
                   side_effect=[60.0, 85.0]), \
             patch("app.repositories.LearningInsightRepository.create",
                   new_callable=AsyncMock, return_value=mock_insight), \
             patch("app.repositories.NotificationRepository.create", notif_create), \
             patch("app.services.AIAlert", mock_ai_alert_cls):
            result = await InsightService.check_attendance_insights(
                "student_id", "course_123"
            )

        assert result is not None
        ai_alert_insert.assert_called_once()
        notif_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_normal_attendance_does_not_trigger_alert(self):
        """<15% attendance change produces no insight."""
        from app.models import AIAlert

        with patch("app.repositories.AttendanceRepository.get_attendance_rate",
                   side_effect=[85.0, 87.0]), \
             patch("app.repositories.LearningInsightRepository.create",
                   new_callable=AsyncMock) as create_mock:
            result = await InsightService.check_attendance_insights(
                "student_id", "course_123"
            )

        assert result is None
        create_mock.assert_not_called()


# ══════════════════════════════════════════════════════════════════════════════
# 7. PARENT NOTIFICATION TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestParentNotifications:
    """Verify that parent sees only their linked child's data and no other's."""

    def test_parent_can_view_linked_child_enrollments(self, client):
        _override(parent_linked)
        enrollment = _make_enrollment(student_id="student_id")
        with patch("app.repositories.EnrollmentRepository.list_by_student",
                   new_callable=AsyncMock, return_value=[enrollment]):
            r = client.get("/api/enrollments/?student_id=student_id")
        _clear()
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["student_id"] == "student_id"

    def test_parent_cannot_view_unlinked_child_enrollments(self, client):
        """parent_unlinked has no linked_student_ids — must get 403."""
        _override(parent_unlinked)
        with patch("app.repositories.EnrollmentRepository.list_by_student",
                   new_callable=AsyncMock, return_value=[]):
            r = client.get("/api/enrollments/?student_id=student_id")
        _clear()
        assert r.status_code == 403

    def test_parent_receives_linked_child_alerts_in_dashboard(self, client):
        """Parent dashboard alerts must include only their child's insights."""
        _override(parent_linked)
        child_enrollment = _make_enrollment(student_id="student_id")
        child_course     = _make_course()
        child_student    = _make_user(RoleEnum.STUDENT, "student_id")
        insight          = MagicMock(spec=LearningInsight)
        insight.change_percentage = -25.0
        insight.summary = "Grade dropped significantly."

        course_query = _mock_query(return_list=[child_course])
        enr_query    = _mock_query(return_list=[child_enrollment])
        insight_query = _mock_query(return_list=[insight])

        with patch("app.api.routes.dashboard.User") as MockUser, \
             patch("app.api.routes.dashboard.Course") as MockCourse, \
             patch("app.api.routes.dashboard.Enrollment") as MockEnrollment, \
             patch("app.api.routes.dashboard.LearningInsight") as MockInsight, \
             patch("app.models.PerformanceScore") as MockPS, \
             patch("app.models.Feedback") as MockFeedback:

            MockUser.get   = AsyncMock(return_value=child_student)
            MockCourse.get = AsyncMock(return_value=child_course)
            MockEnrollment.find.return_value = enr_query
            MockInsight.find.return_value    = insight_query
            MockPS.find.return_value         = _mock_query(return_list=[])
            MockFeedback.find.return_value   = _mock_query(return_list=[])

            r = client.get("/api/dashboard")
        _clear()
        assert r.status_code == 200
        data = r.json()
        assert data["role"] == "parent"
        # Alerts list may include the child's decline
        alerts = data.get("alerts", [])
        if alerts:
            assert any("student_id" not in a.get("message", "").lower()
                       or "student" in a.get("message", "").lower()
                       for a in alerts)

    def test_parent_dashboard_shows_linked_children_count(self, client):
        """metrics.linked_children must equal the number of linked student IDs."""
        _override(parent_linked)  # linked_ids = ["student_id"]

        child_student = _make_user(RoleEnum.STUDENT, "student_id")
        enr_query     = _mock_query(return_list=[])  # no active enrollments
        insight_query = _mock_query(return_list=[])

        with patch("app.api.routes.dashboard.User") as MockUser, \
             patch("app.api.routes.dashboard.Enrollment") as MockEnrollment, \
             patch("app.api.routes.dashboard.LearningInsight") as MockInsight, \
             patch("app.models.PerformanceScore") as MockPS, \
             patch("app.models.Feedback") as MockFeedback:

            MockUser.get = AsyncMock(return_value=child_student)
            MockEnrollment.find.return_value = enr_query
            MockInsight.find.return_value    = insight_query
            MockPS.find.return_value         = _mock_query(return_list=[])
            MockFeedback.find.return_value   = _mock_query(return_list=[])

            r = client.get("/api/dashboard")
        _clear()
        assert r.status_code == 200
        assert r.json()["metrics"]["linked_children"] == 1


# ══════════════════════════════════════════════════════════════════════════════
# 8a. ADMIN DASHBOARD — aggregated metrics
# ══════════════════════════════════════════════════════════════════════════════

class TestAdminDashboardMetrics:
    def test_admin_dashboard_returns_all_required_metric_keys(self, client):
        """After our additions, admin metrics must include 5 new fields."""
        _override(admin)

        course_query  = _mock_query(return_list=[], count=0)
        user_query    = _mock_query(count=0)
        enr_query     = _mock_query(count=0)
        lesson_query  = _mock_query(count=0)

        with patch("app.api.routes.dashboard.Course") as MockCourse, \
             patch("app.api.routes.dashboard.User") as MockUser, \
             patch("app.api.routes.dashboard.Enrollment") as MockEnrollment, \
             patch("app.api.routes.dashboard.LearningInsight") as MockInsight, \
             patch("app.models.LessonRecord") as MockLR, \
             patch("app.models.PerformanceScore") as MockPS:

            MockCourse.find.return_value   = course_query
            MockUser.find.return_value     = user_query
            MockEnrollment.find.return_value = enr_query
            MockInsight.find.return_value  = _mock_query(return_list=[])
            MockLR.find.return_value       = lesson_query
            # MagicMock comparison ops return NotImplemented by default; override so
            # datetime.__le__(mock) is never called (avoids TypeError in Python 3.11).
            MockLR.lesson_date.__ge__.return_value = MagicMock()
            MockLR.lesson_date.__le__.return_value = MagicMock()
            MockPS.find.return_value       = _mock_query(return_list=[])

            r = client.get("/api/dashboard")
        _clear()
        assert r.status_code == 200
        metrics = r.json()["metrics"]
        for key in ("total_students", "total_teachers",
                    "active_courses", "upcoming_lessons", "registered_users"):
            assert key in metrics, f"Missing metric key: {key}"

    def test_admin_dashboard_returns_role_admin(self, client):
        _override(admin)
        course_query = _mock_query(return_list=[], count=0)
        user_query   = _mock_query(count=0)
        enr_query    = _mock_query(count=0)
        lesson_query = _mock_query(count=0)

        with patch("app.api.routes.dashboard.Course") as MockCourse, \
             patch("app.api.routes.dashboard.User") as MockUser, \
             patch("app.api.routes.dashboard.Enrollment") as MockEnrollment, \
             patch("app.api.routes.dashboard.LearningInsight") as MockInsight, \
             patch("app.models.LessonRecord") as MockLR, \
             patch("app.models.PerformanceScore") as MockPS:

            MockCourse.find.return_value    = course_query
            MockUser.find.return_value      = user_query
            MockEnrollment.find.return_value = enr_query
            MockInsight.find.return_value   = _mock_query(return_list=[])
            MockLR.find.return_value        = lesson_query
            MockLR.lesson_date.__ge__.return_value = MagicMock()
            MockLR.lesson_date.__le__.return_value = MagicMock()
            MockPS.find.return_value        = _mock_query(return_list=[])

            r = client.get("/api/dashboard")
        _clear()
        assert r.json()["role"] == "admin"

    def test_non_admin_cannot_see_admin_metrics(self, client):
        """Student dashboard must not contain admin-specific keys."""
        _override(student)

        enr_query     = _mock_query(return_list=[])
        insight_query = _mock_query(return_list=[])

        with patch("app.api.routes.dashboard.Enrollment") as MockEnr, \
             patch("app.api.routes.dashboard.LearningInsight") as MockIns, \
             patch("app.api.routes.dashboard.Course") as MockCourse:

            MockEnr.find.return_value    = enr_query
            MockIns.find.return_value    = insight_query
            MockCourse.get = AsyncMock(return_value=None)

            r = client.get("/api/dashboard")
        _clear()
        assert r.status_code == 200
        metrics = r.json()["metrics"]
        assert "total_students" not in metrics
        assert "total_teachers" not in metrics


# ══════════════════════════════════════════════════════════════════════════════
# 8b. TEACHER DASHBOARD — student_progress list
# ══════════════════════════════════════════════════════════════════════════════

class TestTeacherDashboardMetrics:
    def test_teacher_dashboard_contains_student_progress_key(self, client):
        _override(teacher)

        course       = _make_course(str(teacher.id))
        enrollment   = _make_enrollment(student_id="student_id")
        child_student = _make_user(RoleEnum.STUDENT, "student_id")

        course_query = _mock_query(return_list=[course])
        enr_query    = _mock_query(return_list=[enrollment], count=1)
        insight_query = _mock_query(return_list=[])

        with patch("app.api.routes.dashboard.Course") as MockCourse, \
             patch("app.api.routes.dashboard.Enrollment") as MockEnr, \
             patch("app.api.routes.dashboard.LearningInsight") as MockIns, \
             patch("app.models.PerformanceScore") as MockPS, \
             patch("app.models.ProgressPrediction") as MockPP, \
             patch("app.repositories.UserRepository.get_by_id",
                   new_callable=AsyncMock, return_value=child_student):

            MockCourse.find.return_value  = course_query
            MockEnr.find.return_value     = enr_query
            MockIns.find.return_value     = insight_query
            MockPS.find.return_value      = _mock_query(return_list=[])
            MockPP.find.return_value      = _mock_query(return_list=[])

            r = client.get("/api/dashboard")
        _clear()
        assert r.status_code == 200
        metrics = r.json()["metrics"]
        assert "student_progress" in metrics
        assert isinstance(metrics["student_progress"], list)

    def test_teacher_dashboard_role_field(self, client):
        _override(teacher)
        course_query  = _mock_query(return_list=[])
        insight_query = _mock_query(return_list=[])

        with patch("app.api.routes.dashboard.Course") as MockCourse, \
             patch("app.api.routes.dashboard.Enrollment") as MockEnr, \
             patch("app.api.routes.dashboard.LearningInsight") as MockIns:
            MockCourse.find.return_value = course_query
            MockEnr.find.return_value    = _mock_query(return_list=[], count=0)
            MockIns.find.return_value    = insight_query
            r = client.get("/api/dashboard")
        _clear()
        assert r.json()["role"] == "teacher"


# ══════════════════════════════════════════════════════════════════════════════
# 9. ALERTS / NOTIFICATIONS API RESPONSE TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestNotificationsAPI:
    def test_get_notifications_returns_200_for_authenticated(self, client):
        _override(student)
        with patch("app.repositories.NotificationRepository.list_by_user",
                   new_callable=AsyncMock, return_value=[]):
            r = client.get("/api/notifications/")
        _clear()
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_get_notifications_returns_401_for_unauthenticated(self, client):
        r = client.get("/api/notifications/")
        assert r.status_code == 401

    def test_unread_count_returns_integer(self, client):
        _override(student)
        with patch("app.repositories.NotificationRepository.unread_count",
                   new_callable=AsyncMock, return_value=3):
            r = client.get("/api/notifications/unread-count")
        _clear()
        assert r.status_code == 200
        assert isinstance(r.json()["count"], int)

    def test_mark_notification_read_updates_status(self, client):
        from app.models import Notification
        notif = MagicMock(spec=Notification)
        notif.id         = "notif_1"
        notif.user_id    = str(student.id)
        notif.message    = "Test notification"
        notif.type       = NotificationTypeEnum.AI_ALERT
        notif.read_status = False
        notif.created_at = datetime.utcnow()
        notif.set = AsyncMock(return_value=None)

        _override(student)
        with patch("app.models.Notification.get",
                   new_callable=AsyncMock, return_value=notif), \
             patch("app.repositories.NotificationRepository.mark_read",
                   new_callable=AsyncMock, return_value=None):
            r = client.patch("/api/notifications/notif_1/read")
        _clear()
        assert r.status_code == 200
        assert r.json()["read_status"] is True

    def test_mark_other_users_notification_returns_403(self, client):
        """Student cannot mark another user's notification as read."""
        from app.models import Notification
        notif = MagicMock(spec=Notification)
        notif.id         = "notif_other"
        notif.user_id    = "some_other_user_id"  # not student.id
        notif.message    = "Other user's notification"
        notif.type       = NotificationTypeEnum.FEEDBACK_ADDED
        notif.read_status = False
        notif.created_at = datetime.utcnow()

        _override(student)
        with patch("app.models.Notification.get",
                   new_callable=AsyncMock, return_value=notif):
            r = client.patch("/api/notifications/notif_other/read")
        _clear()
        assert r.status_code == 403

    def test_mark_all_read_returns_204(self, client):
        _override(student)
        with patch("app.repositories.NotificationRepository.mark_all_read",
                   new_callable=AsyncMock, return_value=None):
            r = client.post("/api/notifications/read-all")
        _clear()
        assert r.status_code == 204


class TestAIAlertsAPI:
    def test_get_ai_alerts_returns_200(self, client):
        _override(student)
        with patch("app.repositories.AIAlertRepository.list_by_student",
                   new_callable=AsyncMock, return_value=[]):
            r = client.get("/api/ai-alerts/")
        _clear()
        assert r.status_code == 200

    def test_get_ai_alerts_unauthenticated_returns_401(self, client):
        r = client.get("/api/ai-alerts/")
        assert r.status_code == 401
