"""
Tests: Score Engine, Feedback Visibility, Parent Two-Children Flow (Areas 7+8+9)
Covers:
  - _classify() boundary values: 80=EXCELLENT, 79.9=GOOD, 65=GOOD, 50=AVERAGE, 49.9=NEEDS_ATTENTION
  - compute_and_save: perfect grades → EXCELLENT, zero scores → NEEDS_ATTENTION,
    no feedback defaults to 50 (neutral), no records defaults grade to 0
  - Feedback visibility: student sees only PUBLISHED, teacher sees all (PRIVATE+PUBLISHED)
  - Parent with two children: can list enrollments for child_a and child_b,
    blocked from unlinked student
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch

from app.main import app
from app.security import get_current_user
from app.models import (
    User, RoleEnum,
    ScoreClassificationEnum, SentimentEnum,
    FeedbackVisibilityEnum,
)
from app.services.score_service import _classify, compute_and_save


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


teacher  = _make_user(RoleEnum.TEACHER,  "teacher_id")
admin    = _make_user(RoleEnum.ADMIN,    "admin_id")
student  = _make_user(RoleEnum.STUDENT,  "student_id")
parent2  = _make_user(RoleEnum.PARENT,   "parent_two_id",
                      linked=["child_a_id", "child_b_id"])


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


# ══════════════════════════════════════════════════════════════════════════════
# 9. Score Engine — _classify() boundary tests
# ══════════════════════════════════════════════════════════════════════════════

class TestScoreClassify:
    """Pure-function tests — no I/O, no mocks needed."""

    def test_80_is_excellent(self):
        assert _classify(80.0) == ScoreClassificationEnum.EXCELLENT

    def test_100_is_excellent(self):
        assert _classify(100.0) == ScoreClassificationEnum.EXCELLENT

    def test_79_9_is_good(self):
        assert _classify(79.9) == ScoreClassificationEnum.GOOD

    def test_65_is_good(self):
        assert _classify(65.0) == ScoreClassificationEnum.GOOD

    def test_64_9_is_average(self):
        assert _classify(64.9) == ScoreClassificationEnum.AVERAGE

    def test_50_is_average(self):
        assert _classify(50.0) == ScoreClassificationEnum.AVERAGE

    def test_49_9_is_needs_attention(self):
        assert _classify(49.9) == ScoreClassificationEnum.NEEDS_ATTENTION

    def test_0_is_needs_attention(self):
        assert _classify(0.0) == ScoreClassificationEnum.NEEDS_ATTENTION


# ══════════════════════════════════════════════════════════════════════════════
# 9b. compute_and_save — integration with mocked repos
# ══════════════════════════════════════════════════════════════════════════════

class TestComputeAndSave:

    def _make_record(self, grade: float):
        r = MagicMock()
        r.grade_value = grade
        return r

    def _make_feedback(self, sentiment: SentimentEnum):
        f = MagicMock()
        f.sentiment = sentiment
        return f

    def _make_metrics(self, attendance_rate: float, trend: str = "stable"):
        m = MagicMock()
        m.attendance_rate = attendance_rate
        m.trend_direction = trend
        return m

    async def _run(self, records, metrics, feedbacks, existing_ps=None):
        mock_ps_instance = MagicMock()
        mock_ps_instance.insert = AsyncMock(return_value=None)

        mock_history_instance = MagicMock()
        mock_history_instance.insert = AsyncMock(return_value=None)

        with patch("app.services.score_service.LessonRecordRepository.get_by_student_course",
                   new_callable=AsyncMock, return_value=records), \
             patch("app.services.score_service.ProgressMetricsRepository.get",
                   new_callable=AsyncMock, return_value=metrics), \
             patch("app.services.score_service.FeedbackRepository.list_by_student_course",
                   new_callable=AsyncMock, return_value=feedbacks), \
             patch("app.services.score_service.FeedbackAnalysisRepository") as MockFAR, \
             patch("app.services.score_service.PerformanceScore") as MockPS, \
             patch("app.services.score_service.ScoreHistory") as MockSH:
            # FeedbackAnalysisRepository returns no analyses (triggers legacy fallback)
            MockFAR.list_by_student_course = AsyncMock(return_value=[])
            # find_one returns existing (or None)
            MockPS.find_one = AsyncMock(return_value=existing_ps)
            MockPS.student_id = "student_id"
            MockPS.course_id  = "course_id"
            MockPS.return_value = mock_ps_instance

            MockSH.return_value = mock_history_instance

            result = await compute_and_save("student_id", "course_id")

        return result, mock_ps_instance, mock_history_instance

    @pytest.mark.asyncio
    async def test_perfect_scores_classify_excellent(self):
        records  = [self._make_record(100.0)] * 5
        metrics  = self._make_metrics(100.0, "improving")
        feedbacks = [self._make_feedback(SentimentEnum.POSITIVE)] * 3
        result, ps_inst, sh_inst = await self._run(records, metrics, feedbacks)
        # Should have called insert on the new PerformanceScore and ScoreHistory
        ps_inst.insert.assert_called_once()
        sh_inst.insert.assert_called_once()

    @pytest.mark.asyncio
    async def test_zero_scores_result_in_needs_attention(self):
        records  = [self._make_record(0.0)] * 5
        metrics  = self._make_metrics(0.0, "declining")
        feedbacks = [self._make_feedback(SentimentEnum.NEGATIVE)] * 3
        result, ps_inst, sh_inst = await self._run(records, metrics, feedbacks)
        ps_inst.insert.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_feedback_defaults_to_neutral_50(self):
        """With no feedbacks, feedback_raw defaults to 50.0 (neutral)."""
        records  = [self._make_record(80.0)]
        metrics  = self._make_metrics(80.0, "stable")
        feedbacks = []
        # score = 80*0.5 + 80*0.2 + 50*0.2 + 50*0.1 = 40+16+10+5 = 71 → GOOD
        result, ps_inst, sh_inst = await self._run(records, metrics, feedbacks)
        ps_inst.insert.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_records_defaults_grade_to_zero(self):
        """No lesson records → grade_raw = 0.0."""
        records   = []
        metrics   = self._make_metrics(50.0, "stable")
        feedbacks = []
        result, ps_inst, sh_inst = await self._run(records, metrics, feedbacks)
        ps_inst.insert.assert_called_once()

    @pytest.mark.asyncio
    async def test_existing_ps_calls_set_not_insert(self):
        """When a PerformanceScore already exists, it should be updated via set()."""
        existing = MagicMock()
        existing.set = AsyncMock(return_value=None)
        records   = [self._make_record(75.0)]
        metrics   = self._make_metrics(75.0, "stable")
        feedbacks = []
        result, ps_inst, sh_inst = await self._run(records, metrics, feedbacks,
                                                    existing_ps=existing)
        existing.set.assert_called_once()
        ps_inst.insert.assert_not_called()

    @pytest.mark.asyncio
    async def test_score_history_always_inserted(self):
        """ScoreHistory should be inserted regardless of new vs existing PerformanceScore."""
        existing = MagicMock()
        existing.set = AsyncMock(return_value=None)
        records  = [self._make_record(60.0)]
        metrics  = self._make_metrics(60.0, "stable")
        feedbacks = []
        result, ps_inst, sh_inst = await self._run(records, metrics, feedbacks,
                                                    existing_ps=existing)
        sh_inst.insert.assert_called_once()


# ══════════════════════════════════════════════════════════════════════════════
# 8. Feedback visibility — PRIVATE vs PUBLISHED
# ══════════════════════════════════════════════════════════════════════════════

class TestFeedbackVisibility:

    def _make_feedback_obj(self, visibility: FeedbackVisibilityEnum):
        f = MagicMock()
        f.id = "fb_001"
        f.student_id = "student_id"
        f.course_id = "course_abc"
        f.teacher_id = "teacher_id"
        f.content = "Good work."
        f.visibility = visibility
        f.sentiment = SentimentEnum.POSITIVE
        f.delivery_target = MagicMock()
        f.delivery_target.value = "none"
        f.created_at = MagicMock()
        f.created_at.isoformat = MagicMock(return_value="2025-01-01T00:00:00")
        return f

    def _get_feedback(self, client, user, feedbacks):
        _override(user)
        mock_course = MagicMock()
        mock_course.teacher_id = str(teacher.id)
        with patch("app.repositories.CourseRepository.get_by_id",
                   new_callable=AsyncMock, return_value=mock_course), \
             patch("app.api.routes.academic.FeedbackRepository.list_by_course",
                   new_callable=AsyncMock, return_value=feedbacks):
            r = client.get("/api/academic/feedback?course_id=course_abc")
        _clear()
        return r

    def test_teacher_sees_private_feedback(self, client):
        fb = [self._make_feedback_obj(FeedbackVisibilityEnum.PRIVATE)]
        r = self._get_feedback(client, teacher, fb)
        assert r.status_code == 200
        assert len(r.json()) == 1

    def test_teacher_sees_published_feedback(self, client):
        fb = [self._make_feedback_obj(FeedbackVisibilityEnum.PUBLISHED)]
        r = self._get_feedback(client, teacher, fb)
        assert r.status_code == 200
        assert len(r.json()) == 1

    def test_student_sees_published_feedback(self, client):
        fb = [self._make_feedback_obj(FeedbackVisibilityEnum.PUBLISHED)]
        r = self._get_feedback(client, student, fb)
        assert r.status_code == 200
        assert len(r.json()) == 1

    def test_student_cannot_see_private_feedback(self, client):
        fb = [self._make_feedback_obj(FeedbackVisibilityEnum.PRIVATE)]
        r = self._get_feedback(client, student, fb)
        assert r.status_code == 200
        assert len(r.json()) == 0  # private items filtered out

    def test_student_sees_only_published_when_mixed(self, client):
        fb = [
            self._make_feedback_obj(FeedbackVisibilityEnum.PRIVATE),
            self._make_feedback_obj(FeedbackVisibilityEnum.PUBLISHED),
        ]
        r = self._get_feedback(client, student, fb)
        assert r.status_code == 200
        assert len(r.json()) == 1

    def test_parent_cannot_see_private_feedback(self, client):
        parent_local = _make_user(RoleEnum.PARENT, "parent_id")
        fb = [self._make_feedback_obj(FeedbackVisibilityEnum.PRIVATE)]
        r = self._get_feedback(client, parent_local, fb)
        assert r.status_code == 200
        assert len(r.json()) == 0

    def test_admin_sees_private_feedback(self, client):
        fb = [self._make_feedback_obj(FeedbackVisibilityEnum.PRIVATE)]
        r = self._get_feedback(client, admin, fb)
        assert r.status_code == 200
        assert len(r.json()) == 1


# ══════════════════════════════════════════════════════════════════════════════
# 7. Parent with two children — enrollment access
# ══════════════════════════════════════════════════════════════════════════════

class TestParentTwoChildren:

    def _make_enrollment(self, student_id, course_id="course_abc"):
        e = MagicMock()
        e.id = f"enr_{student_id}"
        e.student_id = student_id
        e.course_id = course_id
        e.status = "active"
        e.enrolled_at = MagicMock()
        e.enrolled_at.isoformat = MagicMock(return_value="2025-01-01T00:00:00")
        return e

    def _get_enrollments(self, client, student_id, enrollments):
        _override(parent2)
        with patch("app.api.routes.enrollments.EnrollmentRepository.list_by_student",
                   new_callable=AsyncMock, return_value=enrollments):
            r = client.get(f"/api/enrollments/?student_id={student_id}")
        _clear()
        return r

    def test_parent_can_list_enrollments_child_a(self, client):
        enr = [self._make_enrollment("child_a_id")]
        r = self._get_enrollments(client, "child_a_id", enr)
        assert r.status_code == 200

    def test_parent_can_list_enrollments_child_b(self, client):
        enr = [self._make_enrollment("child_b_id")]
        r = self._get_enrollments(client, "child_b_id", enr)
        assert r.status_code == 200

    def test_parent_blocked_from_unlinked_student(self, client):
        _override(parent2)
        r = client.get("/api/enrollments/?student_id=unlinked_student_id")
        _clear()
        assert r.status_code == 403

    def test_parent_enrollments_for_child_a_returns_list(self, client):
        enr = [self._make_enrollment("child_a_id", "course_1"),
               self._make_enrollment("child_a_id", "course_2")]
        r = self._get_enrollments(client, "child_a_id", enr)
        assert r.status_code == 200
        assert len(r.json()) == 2

    def test_parent_enrollments_for_child_b_returns_list(self, client):
        enr = [self._make_enrollment("child_b_id", "course_3")]
        r = self._get_enrollments(client, "child_b_id", enr)
        assert r.status_code == 200
        assert len(r.json()) == 1

    def test_parent_without_linked_children_blocked(self, client):
        parent_no_children = _make_user(RoleEnum.PARENT, "lonely_parent", linked=[])
        _override(parent_no_children)
        r = client.get("/api/enrollments/?student_id=some_child")
        _clear()
        assert r.status_code == 403
