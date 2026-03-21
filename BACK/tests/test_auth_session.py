"""
Tests: Login / Auth Session Flow (Area 1)
Covers:
  - Email+password login (valid, wrong password, inactive, no hash)
  - Session token issuance, logout, refresh
  - /api/auth/me RBAC
  - Signup (new user, duplicate email)
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch
from passlib.context import CryptContext

from app.main import app
from app.security import get_current_user
from app.models import User, RoleEnum

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
TEST_PASSWORD = "securepass99"
TEST_HASH = _pwd.hash(TEST_PASSWORD)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_db_user(
    uid="user_001",
    email="alice@test.com",
    role=RoleEnum.TEACHER,
    is_active=True,
    hashed_password=None,
    is_approved=True,
) -> User:
    u = MagicMock(spec=User)
    u.id = uid
    u.firebase_uid = email
    u.email = email
    u.first_name = "Alice"
    u.last_name = "Smith"
    u.display_name = None
    u.role = role
    u.avatar_url = None
    u.linked_student_ids = []
    u.is_active = is_active
    u.is_approved = is_approved
    u.deleted_at = None
    u.created_at = __import__("datetime").datetime.utcnow()
    u.hashed_password = hashed_password or TEST_HASH
    u.session_token = "old-token-abc"
    u.set = AsyncMock(return_value=None)
    u.full_name = MagicMock(return_value="Alice Smith")
    return u


def _override(user):
    async def _dep():
        return user
    app.dependency_overrides[get_current_user] = _dep


def _clear():
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


# ══════════════════════════════════════════════════════════════════════════════
# 1a. Login flow
# ══════════════════════════════════════════════════════════════════════════════

class TestLoginFlow:

    def test_valid_login_returns_access_token(self, client):
        db_user = _make_db_user()
        with patch("app.repositories.UserRepository.get_by_email",
                   new_callable=AsyncMock, return_value=db_user):
            r = client.post("/api/auth/login",
                            json={"email": "alice@test.com", "password": TEST_PASSWORD})
        assert r.status_code == 200
        body = r.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"
        assert len(body["access_token"]) > 10

    def test_wrong_password_returns_401(self, client):
        db_user = _make_db_user()
        with patch("app.repositories.UserRepository.get_by_email",
                   new_callable=AsyncMock, return_value=db_user):
            r = client.post("/api/auth/login",
                            json={"email": "alice@test.com", "password": "wrongpass1"})
        assert r.status_code == 401
        assert "credentials" in r.json()["detail"].lower()

    def test_nonexistent_user_returns_401(self, client):
        with patch("app.repositories.UserRepository.get_by_email",
                   new_callable=AsyncMock, return_value=None):
            r = client.post("/api/auth/login",
                            json={"email": "nobody@test.com", "password": TEST_PASSWORD})
        assert r.status_code == 401

    def test_inactive_user_returns_401(self, client):
        db_user = _make_db_user(is_active=False)
        with patch("app.repositories.UserRepository.get_by_email",
                   new_callable=AsyncMock, return_value=db_user):
            r = client.post("/api/auth/login",
                            json={"email": "alice@test.com", "password": TEST_PASSWORD})
        assert r.status_code == 401

    def test_unapproved_user_returns_403(self, client):
        """User who registered but has not been approved by admin cannot log in.
        Approval check runs before is_active check so new users see the helpful message."""
        db_user = _make_db_user(is_active=False, is_approved=False)
        with patch("app.repositories.UserRepository.get_by_email",
                   new_callable=AsyncMock, return_value=db_user):
            r = client.post("/api/auth/login",
                            json={"email": "alice@test.com", "password": TEST_PASSWORD})
        assert r.status_code == 403
        assert "pending" in r.json()["detail"].lower()

    def test_active_but_unapproved_user_returns_403(self, client):
        """If somehow is_active=True but is_approved=False, login must return 403."""
        db_user = _make_db_user(is_active=True, is_approved=False)
        with patch("app.repositories.UserRepository.get_by_email",
                   new_callable=AsyncMock, return_value=db_user):
            r = client.post("/api/auth/login",
                            json={"email": "alice@test.com", "password": TEST_PASSWORD})
        assert r.status_code == 403
        assert "pending" in r.json()["detail"].lower()

    def test_user_with_no_stored_password_returns_401(self, client):
        """Account created via Firebase with no hashed_password."""
        db_user = _make_db_user(hashed_password=None)
        db_user.hashed_password = None
        with patch("app.repositories.UserRepository.get_by_email",
                   new_callable=AsyncMock, return_value=db_user):
            r = client.post("/api/auth/login",
                            json={"email": "alice@test.com", "password": TEST_PASSWORD})
        assert r.status_code == 401

    def test_login_issues_new_token_each_time(self, client):
        """Two login calls → two different tokens."""
        db_user = _make_db_user()
        with patch("app.repositories.UserRepository.get_by_email",
                   new_callable=AsyncMock, return_value=db_user):
            r1 = client.post("/api/auth/login",
                             json={"email": "alice@test.com", "password": TEST_PASSWORD})
            r2 = client.post("/api/auth/login",
                             json={"email": "alice@test.com", "password": TEST_PASSWORD})
        assert r1.json()["access_token"] != r2.json()["access_token"]


# ══════════════════════════════════════════════════════════════════════════════
# 1b. /api/auth/me
# ══════════════════════════════════════════════════════════════════════════════

class TestGetMe:

    def test_get_me_without_token_returns_401(self, client):
        _clear()
        r = client.get("/api/auth/me")
        assert r.status_code == 401

    def test_get_me_returns_correct_role_and_email(self, client):
        db_user = _make_db_user(role=RoleEnum.TEACHER)
        _override(db_user)
        r = client.get("/api/auth/me")
        _clear()
        assert r.status_code == 200
        data = r.json()
        assert data["email"] == "alice@test.com"
        assert data["role"] == "teacher"

    def test_get_me_student_has_empty_linked_students(self, client):
        db_user = _make_db_user(role=RoleEnum.STUDENT)
        _override(db_user)
        r = client.get("/api/auth/me")
        _clear()
        assert r.status_code == 200
        assert r.json()["linked_student_ids"] == []

    def test_get_me_parent_shows_linked_student_ids(self, client):
        db_user = _make_db_user(role=RoleEnum.PARENT)
        db_user.linked_student_ids = ["child_001", "child_002"]
        _override(db_user)
        r = client.get("/api/auth/me")
        _clear()
        assert r.status_code == 200
        assert "child_001" in r.json()["linked_student_ids"]


# ══════════════════════════════════════════════════════════════════════════════
# 1c. Logout and refresh token
# ══════════════════════════════════════════════════════════════════════════════

class TestLogoutRefresh:

    def test_logout_requires_auth(self, client):
        _clear()
        r = client.post("/api/auth/logout")
        assert r.status_code == 401

    def test_logout_clears_session_token(self, client):
        db_user = _make_db_user()
        _override(db_user)
        r = client.post("/api/auth/logout")
        _clear()
        assert r.status_code == 200
        # Verify set was called with None to clear session token
        db_user.set.assert_called_once()
        call_arg = db_user.set.call_args[0][0]
        # The value associated with the session_token key must be None
        values = list(call_arg.values())
        assert None in values

    def test_refresh_token_returns_new_token(self, client):
        db_user = _make_db_user()
        _override(db_user)
        r = client.post("/api/auth/refresh-token")
        _clear()
        assert r.status_code == 200
        body = r.json()
        assert "access_token" in body
        # Token must be different from the old one
        assert body["access_token"] != "old-token-abc"

    def test_refresh_token_requires_auth(self, client):
        _clear()
        r = client.post("/api/auth/refresh-token")
        assert r.status_code == 401


# ══════════════════════════════════════════════════════════════════════════════
# 1d. Signup
# ══════════════════════════════════════════════════════════════════════════════

class TestSignup:

    def test_signup_with_existing_email_returns_400(self, client):
        existing = _make_db_user()
        with patch("app.repositories.UserRepository.get_by_email",
                   new_callable=AsyncMock, return_value=existing):
            r = client.post("/api/auth/signup", json={
                "email": "alice@test.com",
                "password": TEST_PASSWORD,
                "first_name": "Alice",
                "last_name": "Smith",
                "role": "teacher",
            })
        assert r.status_code == 400
        assert "already registered" in r.json()["detail"].lower()

    def test_signup_new_user_returns_pending(self, client):
        """New self-registrations require admin approval — returns 202 with pending status."""
        mock_new_user = MagicMock()
        mock_new_user.insert = AsyncMock(return_value=None)
        with patch("app.repositories.UserRepository.get_by_email",
                   new_callable=AsyncMock, return_value=None), \
             patch("app.api.routes.auth.User", return_value=mock_new_user):
            r = client.post("/api/auth/signup", json={
                "email": "newuser@test.com",
                "password": TEST_PASSWORD,
                "first_name": "Bob",
                "last_name": "Jones",
                "role": "student",
            })
        assert r.status_code == 202
        body = r.json()
        assert body["status"] == "pending"
        assert "message" in body

    def test_signup_password_too_short_returns_422(self, client):
        r = client.post("/api/auth/signup", json={
            "email": "short@test.com",
            "password": "short",  # < 8 chars
            "first_name": "A",
            "last_name": "B",
            "role": "student",
        })
        assert r.status_code == 422

    def test_signup_invalid_role_returns_422(self, client):
        r = client.post("/api/auth/signup", json={
            "email": "user@test.com",
            "password": TEST_PASSWORD,
            "first_name": "A",
            "last_name": "B",
            "role": "superuser",  # invalid role
        })
        assert r.status_code == 422
