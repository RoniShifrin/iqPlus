"""
Tests: Weekly Scheduler Jobs + Email Service Payload Validation (Areas 3 & 4)
Covers:
  - _run_weekly_summaries: empty enrollments, lesson records processing, email to teacher
  - _process_enrollment: no records → early return; low engagement/absence notes
  - _run_feedback_digest: no feedback; delivery to student; delivery to parent
  - EmailNotificationService: no-SMTP fallback, subject formats, payload contents
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _make_lesson_record(grade=85.0, status="present", engagement=4.0,
                        difficulty="medium", feedback="Good work."):
    r = MagicMock()
    r.grade_value = grade
    r.attendance_status = MagicMock(value=status)
    r.engagement_rating = engagement
    r.difficulty_level = MagicMock(value=difficulty)
    r.teacher_feedback = feedback
    return r


def _make_user(email="teacher@test.com", full_name="T Smith", linked_ids=None):
    u = MagicMock()
    u.email = email
    u.linked_student_ids = linked_ids or []
    u.full_name = MagicMock(return_value=full_name)
    return u


def _make_course(name="Math 101", teacher_id="teacher_id"):
    c = MagicMock()
    c.name = name
    c.teacher_id = teacher_id
    return c


def _make_metrics(trend="stable"):
    m = MagicMock()
    m.trend_direction = trend
    m.attendance_rate = 80.0
    return m


def _make_feedback(student_id="s1", course_id="c1", delivery="student", sentiment="positive", content="Great!"):
    f = MagicMock()
    f.student_id = student_id
    f.course_id = course_id
    f.delivery_target = MagicMock(value=delivery)
    f.sentiment = MagicMock(value=sentiment)
    f.content = content
    f.submitted_at = datetime.utcnow()
    return f


# ══════════════════════════════════════════════════════════════════════════════
# 3a. Weekly summary job
# ══════════════════════════════════════════════════════════════════════════════

class TestWeeklySummaryJob:

    @pytest.mark.asyncio
    async def test_empty_enrollments_completes_without_crash(self):
        from app.services.scheduler import _run_weekly_summaries

        mock_query = MagicMock()
        mock_query.to_list = AsyncMock(return_value=[])

        with patch("app.models.Enrollment") as MockEnr:
            MockEnr.find.return_value = mock_query
            await _run_weekly_summaries()  # Must not raise

    @pytest.mark.asyncio
    async def test_enrollment_with_no_lesson_records_returns_early(self):
        """_process_enrollment should short-circuit when no records exist."""
        from app.services.scheduler import _process_enrollment

        with patch("app.repositories.LessonRecordRepository.get_by_student_course",
                   new_callable=AsyncMock, return_value=[]):
            # Should not crash and should NOT call WeeklySummaryRepository.create
            with patch("app.repositories.WeeklySummaryRepository.create",
                       new_callable=AsyncMock) as mock_create:
                await _process_enrollment("s1", "c1", datetime.utcnow())
                mock_create.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_enrollment_creates_weekly_summary(self):
        """When records exist a WeeklySummary is created."""
        from app.services.scheduler import _process_enrollment

        records = [_make_lesson_record(grade=90.0, status="present")]
        mock_summary = MagicMock()
        mock_summary.set = AsyncMock(return_value=None)

        teacher_user = _make_user(email="teacher@test.com")
        student_user = _make_user(email="student@test.com", full_name="Student One")
        course = _make_course()

        with patch("app.repositories.LessonRecordRepository.get_by_student_course",
                   new_callable=AsyncMock, return_value=records), \
             patch("app.repositories.ProgressMetricsRepository.get",
                   new_callable=AsyncMock, return_value=_make_metrics()), \
             patch("app.repositories.AIAlertRepository.list_by_student_course",
                   new_callable=AsyncMock, return_value=[]), \
             patch("app.repositories.WeeklySummaryRepository.create",
                   new_callable=AsyncMock, return_value=mock_summary) as mock_create, \
             patch("app.repositories.UserRepository.get_by_id",
                   new_callable=AsyncMock, side_effect=[student_user, teacher_user]), \
             patch("app.models.Course") as MockCourse, \
             patch("app.models.User") as MockUser, \
             patch("app.services.email_service.EmailNotificationService.send_weekly_report",
                   return_value=False):
            MockCourse.get = AsyncMock(return_value=course)
            MockUser.find.return_value.to_list = AsyncMock(return_value=[])

            await _process_enrollment("s1", "c1", datetime.utcnow())

        mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_enrollment_sends_email_to_teacher(self):
        from app.services.scheduler import _process_enrollment

        records = [_make_lesson_record()]
        mock_summary = MagicMock()
        mock_summary.set = AsyncMock(return_value=None)
        teacher_user = _make_user(email="teacher@test.com")
        student_user = _make_user(email="student@test.com", full_name="Alice B")
        course = _make_course(teacher_id="teacher_id")

        with patch("app.repositories.LessonRecordRepository.get_by_student_course",
                   new_callable=AsyncMock, return_value=records), \
             patch("app.repositories.ProgressMetricsRepository.get",
                   new_callable=AsyncMock, return_value=_make_metrics()), \
             patch("app.repositories.AIAlertRepository.list_by_student_course",
                   new_callable=AsyncMock, return_value=[]), \
             patch("app.repositories.WeeklySummaryRepository.create",
                   new_callable=AsyncMock, return_value=mock_summary), \
             patch("app.repositories.UserRepository.get_by_id",
                   new_callable=AsyncMock, side_effect=[student_user, teacher_user]), \
             patch("app.models.Course") as MockCourse, \
             patch("app.models.User") as MockUser, \
             patch("app.services.email_service.EmailNotificationService.send_weekly_report",
                   return_value=True) as mock_email:
            MockCourse.get = AsyncMock(return_value=course)
            MockUser.find.return_value.to_list = AsyncMock(return_value=[])

            await _process_enrollment("s1", "c1", datetime.utcnow())

        mock_email.assert_called_once()
        call_kw = mock_email.call_args[1]
        assert call_kw["recipient_email"] == "teacher@test.com"

    @pytest.mark.asyncio
    async def test_process_enrollment_low_engagement_adds_pattern_note(self):
        """Avg engagement < 2.5 should add a note to ai_observations."""
        from app.services.scheduler import _process_enrollment

        records = [
            _make_lesson_record(engagement=2.0),
            _make_lesson_record(engagement=1.5),
        ]
        mock_summary = MagicMock()
        mock_summary.set = AsyncMock(return_value=None)
        student_user = _make_user(email="student@test.com")
        teacher_user = _make_user(email="t@test.com")
        course = _make_course()

        captured_kw = {}

        async def _capture_create(**kwargs):
            captured_kw.update(kwargs)
            return mock_summary

        with patch("app.repositories.LessonRecordRepository.get_by_student_course",
                   new_callable=AsyncMock, return_value=records), \
             patch("app.repositories.ProgressMetricsRepository.get",
                   new_callable=AsyncMock, return_value=_make_metrics()), \
             patch("app.repositories.AIAlertRepository.list_by_student_course",
                   new_callable=AsyncMock, return_value=[]), \
             patch("app.repositories.WeeklySummaryRepository.create",
                   side_effect=_capture_create), \
             patch("app.repositories.UserRepository.get_by_id",
                   new_callable=AsyncMock, side_effect=[student_user, teacher_user]), \
             patch("app.models.Course") as MockCourse, \
             patch("app.models.User") as MockUser, \
             patch("app.services.email_service.EmailNotificationService.send_weekly_report",
                   return_value=False):
            MockCourse.get = AsyncMock(return_value=course)
            MockUser.find.return_value.to_list = AsyncMock(return_value=[])

            await _process_enrollment("s1", "c1", datetime.utcnow())

        ai_obs = captured_kw.get("ai_observations", "") or ""
        assert "engagement" in ai_obs.lower()


# ══════════════════════════════════════════════════════════════════════════════
# 3b. Feedback digest job
# ══════════════════════════════════════════════════════════════════════════════

class TestFeedbackDigestJob:

    @pytest.mark.asyncio
    async def test_no_feedback_this_week_no_emails_sent(self):
        from app.services.scheduler import _run_feedback_digest

        mock_query = MagicMock()
        mock_query.to_list = AsyncMock(return_value=[])

        with patch("app.models.Feedback") as MockFeedback, \
             patch("app.services.email_service.EmailNotificationService.send_email",
                   return_value=False) as mock_email:
            MockFeedback.find.return_value = mock_query
            await _run_feedback_digest()

        mock_email.assert_not_called()

    @pytest.mark.asyncio
    async def test_feedback_digest_sends_to_student_when_delivery_student(self):
        from app.services.scheduler import _run_feedback_digest

        feedback = _make_feedback(student_id="s1", course_id="c1", delivery="student")
        mock_query = MagicMock()
        mock_query.to_list = AsyncMock(return_value=[feedback])

        student_user = _make_user(email="student@test.com", full_name="Student A")
        student_user.email = "student@test.com"
        student_user.linked_student_ids = []
        course = _make_course(name="Math 101")

        with patch("app.models.Feedback") as MockFb, \
             patch("app.models.User") as MockUser, \
             patch("app.models.Course") as MockCourse, \
             patch("app.services.email_service.EmailNotificationService.send_email",
                   return_value=True) as mock_email:
            # submitted_at >= week_start comparison: configure __ge__ to avoid TypeError
            MockFb.submitted_at.__ge__.return_value = MagicMock()
            MockFb.find.return_value = mock_query
            MockUser.get = AsyncMock(return_value=student_user)
            MockCourse.get = AsyncMock(return_value=course)
            MockUser.find.return_value.to_list = AsyncMock(return_value=[])

            await _run_feedback_digest()

        mock_email.assert_called_once()
        call_kw = mock_email.call_args[1]
        assert call_kw["recipient"] == "student@test.com"
        assert "Feedback" in call_kw["subject"]

    @pytest.mark.asyncio
    async def test_feedback_digest_sends_to_parent_for_linked_child(self):
        from app.services.scheduler import _run_feedback_digest

        feedback = _make_feedback(student_id="s1", course_id="c1", delivery="parent")
        mock_query = MagicMock()
        mock_query.to_list = AsyncMock(return_value=[feedback])

        student_user = _make_user(email="student@test.com", full_name="Student B")
        parent_user = _make_user(email="parent@test.com")
        parent_user.linked_student_ids = ["s1"]
        course = _make_course()

        with patch("app.models.Feedback") as MockFb, \
             patch("app.models.User") as MockUser, \
             patch("app.models.Course") as MockCourse, \
             patch("app.services.email_service.EmailNotificationService.send_email",
                   return_value=True) as mock_email:
            MockFb.submitted_at.__ge__.return_value = MagicMock()
            MockFb.find.return_value = mock_query
            MockUser.get = AsyncMock(return_value=student_user)
            MockCourse.get = AsyncMock(return_value=course)
            MockUser.find.return_value.to_list = AsyncMock(return_value=[parent_user])

            await _run_feedback_digest()

        mock_email.assert_called_once()
        assert mock_email.call_args[1]["recipient"] == "parent@test.com"

    @pytest.mark.asyncio
    async def test_feedback_digest_skips_missing_student_gracefully(self):
        from app.services.scheduler import _run_feedback_digest

        feedback = _make_feedback()
        mock_query = MagicMock()
        mock_query.to_list = AsyncMock(return_value=[feedback])

        with patch("app.models.Feedback") as MockFb, \
             patch("app.models.User") as MockUser, \
             patch("app.models.Course") as MockCourse, \
             patch("app.services.email_service.EmailNotificationService.send_email") as mock_email:
            MockFb.find.return_value = mock_query
            MockUser.get = AsyncMock(return_value=None)  # student not found
            MockCourse.get = AsyncMock(return_value=None)

            await _run_feedback_digest()  # Must not raise

        mock_email.assert_not_called()


# ══════════════════════════════════════════════════════════════════════════════
# 4. Email Service payload validation
# ══════════════════════════════════════════════════════════════════════════════

class TestEmailServicePayloads:
    """No real SMTP — validate subject/body format and no-config fallback."""

    def test_send_email_no_smtp_config_returns_false(self):
        from app.services.email_service import EmailNotificationService
        with patch.object(EmailNotificationService, "SMTP_USER", ""), \
             patch.object(EmailNotificationService, "SMTP_PASSWORD", ""):
            result = EmailNotificationService.send_email(
                recipient="x@test.com", subject="Test", html_content="<p>Hi</p>"
            )
        assert result is False

    def test_send_weekly_report_no_smtp_returns_false(self):
        from app.services.email_service import EmailNotificationService
        with patch.object(EmailNotificationService, "SMTP_USER", ""), \
             patch.object(EmailNotificationService, "SMTP_PASSWORD", ""):
            result = EmailNotificationService.send_weekly_report(
                recipient_email="t@test.com", student_name="Alice", course_name="Math",
                present=5, absent=1, avg_grade=88.0, trend="improving",
                feedback_highlights=["Good week!"],
            )
        assert result is False

    def test_send_weekly_report_correct_subject_includes_student_and_course(self):
        from app.services.email_service import EmailNotificationService
        with patch.object(EmailNotificationService, "SMTP_USER", "from@test.com"), \
             patch.object(EmailNotificationService, "SMTP_PASSWORD", "pwd"), \
             patch.object(EmailNotificationService, "_send_smtp") as mock_smtp:
            EmailNotificationService.send_weekly_report(
                recipient_email="r@test.com", student_name="Bob Lee",
                course_name="Science", present=3, absent=0,
                avg_grade=92.0, trend="improving", feedback_highlights=[],
            )
        subj = mock_smtp.call_args[0][1]
        assert "Bob Lee" in subj
        assert "Science" in subj

    def test_send_performance_warning_subject_contains_student_name(self):
        from app.services.email_service import EmailNotificationService
        with patch.object(EmailNotificationService, "SMTP_USER", "u@test.com"), \
             patch.object(EmailNotificationService, "SMTP_PASSWORD", "p"), \
             patch.object(EmailNotificationService, "_send_smtp") as mock_smtp:
            EmailNotificationService.send_performance_warning(
                recipient_email="t@test.com", student_name="Carol D",
                course_name="History", current_score=42.0, classification="needs_attention",
            )
        subj = mock_smtp.call_args[0][1]
        assert "Carol D" in subj
        assert "Warning" in subj or "warning" in subj.lower()

    def test_send_improvement_notification_body_includes_score_delta(self):
        from app.services.email_service import EmailNotificationService
        with patch.object(EmailNotificationService, "SMTP_USER", "u@test.com"), \
             patch.object(EmailNotificationService, "SMTP_PASSWORD", "p"), \
             patch.object(EmailNotificationService, "_send_smtp") as mock_smtp:
            EmailNotificationService.send_improvement_notification(
                recipient_email="t@test.com", student_name="Dave",
                course_name="Physics", previous_score=55.0, current_score=80.0,
            )
        body = mock_smtp.call_args[0][2]
        assert "55" in body and "80" in body  # both scores present
        assert "25" in body or "+25" in body  # delta mentioned

    def test_send_teacher_feedback_notification_positive_uses_green_color(self):
        from app.services.email_service import EmailNotificationService
        with patch.object(EmailNotificationService, "SMTP_USER", "u@test.com"), \
             patch.object(EmailNotificationService, "SMTP_PASSWORD", "p"), \
             patch.object(EmailNotificationService, "_send_smtp") as mock_smtp:
            EmailNotificationService.send_teacher_feedback_notification(
                recipient_email="s@test.com", student_name="Eva",
                course_name="Art", sentiment="positive",
                feedback_preview="Excellent work!",
            )
        body = mock_smtp.call_args[0][2]
        assert "#16a34a" in body  # green color for positive sentiment

    def test_send_teacher_feedback_notification_negative_uses_red_color(self):
        from app.services.email_service import EmailNotificationService
        with patch.object(EmailNotificationService, "SMTP_USER", "u@test.com"), \
             patch.object(EmailNotificationService, "SMTP_PASSWORD", "p"), \
             patch.object(EmailNotificationService, "_send_smtp") as mock_smtp:
            EmailNotificationService.send_teacher_feedback_notification(
                recipient_email="s@test.com", student_name="Frank",
                course_name="PE", sentiment="negative",
                feedback_preview="Needs improvement.",
            )
        body = mock_smtp.call_args[0][2]
        assert "#dc2626" in body  # red color for negative

    def test_send_email_smtp_exception_returns_false_not_raised(self):
        from app.services.email_service import EmailNotificationService
        with patch.object(EmailNotificationService, "SMTP_USER", "u@test.com"), \
             patch.object(EmailNotificationService, "SMTP_PASSWORD", "p"), \
             patch.object(EmailNotificationService, "_send_smtp",
                          side_effect=Exception("SMTP connection refused")):
            result = EmailNotificationService.send_email(
                recipient="t@test.com", subject="S", html_content="<p>X</p>"
            )
        assert result is False  # exception swallowed, returns False

    def test_send_batch_notifications_no_config_counts_all_as_failed(self):
        from app.services.email_service import EmailNotificationService
        insights = [
            {"recipient_email": "a@test.com", "student_name": "A", "course_name": "C",
             "summary": "Drop", "insight_type": "grade_drop", "recommendation": "Review"},
            {"recipient_email": "b@test.com", "student_name": "B", "course_name": "C",
             "summary": "Up", "insight_type": "improvement", "recommendation": "Keep it up"},
        ]
        with patch.object(EmailNotificationService, "SMTP_USER", ""), \
             patch.object(EmailNotificationService, "SMTP_PASSWORD", ""):
            result = EmailNotificationService.send_batch_notifications(insights)
        assert result["failed"] == 2
        assert result["sent"] == 0
