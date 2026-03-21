"""
Shared pytest configuration.
Patches MongoDB lifespan startup so TestClient works without a real DB connection.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _setup_beanie_expression_fields():
    """
    Beanie ExpressionFields (used as dict keys in Document.set() calls) are
    normally populated by init_beanie.  Since we mock init_beanie in tests,
    we inject them manually so that code like `{User.session_token: value}`
    works without a real MongoDB connection.
    """
    from beanie.odm.fields import ExpressionField
    from app.models import User, PerformanceScore, Syllabus, ScoreHistory

    for model, field_name in [
        (User, "session_token"),
        (User, "is_active"),
        (PerformanceScore, "score"),
        (PerformanceScore, "classification"),
        (PerformanceScore, "grade_score"),
        (PerformanceScore, "attendance_score"),
        (PerformanceScore, "feedback_score"),
        (PerformanceScore, "trend_score"),
        (PerformanceScore, "computed_at"),
        (PerformanceScore, "student_id"),
        (PerformanceScore, "course_id"),
        (Syllabus, "status"),
        (Syllabus, "topics"),
    ]:
        try:
            getattr(model, field_name)
        except AttributeError:
            # Bypass Pydantic V2's ModelMetaclass.__setattr__ to inject the field
            type.__setattr__(model, field_name, ExpressionField(field_name))


@pytest.fixture(scope="session", autouse=True)
def mock_mongo_lifespan():
    """
    Session-scoped mock that intercepts MongoDB init and APScheduler
    so TestClient lifespan runs cleanly without a real Atlas connection.
    """
    mock_motor_client = MagicMock()
    mock_motor_client.__getitem__ = MagicMock(return_value=MagicMock())
    mock_motor_client.close = MagicMock()

    with (
        patch("app.main.AsyncIOMotorClient", return_value=mock_motor_client),
        patch("app.main.init_beanie", new_callable=AsyncMock),
        patch("app.services.scheduler.start_scheduler", MagicMock()),
        patch("app.services.scheduler.stop_scheduler", MagicMock()),
    ):
        _setup_beanie_expression_fields()
        yield
