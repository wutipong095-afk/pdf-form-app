"""เส้นทางเข้าสู่ระบบด้วย Google — mock token ไม่ยิงเน็ต"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ["AUTH_REQUIRED"] = "false"
if "pfm-tests-" not in os.environ.get("DATA_DIR", ""):
    _TEST_DATA_DIR = Path(tempfile.mkdtemp(prefix="pfm-tests-"))
    os.environ["DATA_DIR"] = str(_TEST_DATA_DIR)
    os.environ["LOG_DIR"] = str(_TEST_DATA_DIR / "logs")
else:
    _TEST_DATA_DIR = Path(os.environ["DATA_DIR"])

import app as A  # noqa: E402


@pytest.fixture()
def google_env(monkeypatch, tmp_path):
    monkeypatch.setattr(A, "AUTH_REQUIRED", True)
    monkeypatch.setattr(A, "DATA_DIR", tmp_path)
    monkeypatch.setattr(A, "USERS_DIR", tmp_path / "users")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-client-secret")
    monkeypatch.delenv("GOOGLE_ALLOWED_DOMAINS", raising=False)
    monkeypatch.delenv("GOOGLE_SIGNUP", raising=False)
    (tmp_path / "users").mkdir()
    return tmp_path


@pytest.fixture()
def client(google_env):
    return A.app.test_client()


def _token(email="alice@school.ac.th", sub="gid-1", verified=True, name="Alice"):
    return {
        "userinfo": {
            "sub": sub,
            "email": email,
            "email_verified": verified,
            "name": name,
        }
    }


def test_login_hides_google_when_not_configured(monkeypatch, tmp_path):
    monkeypatch.setattr(A, "AUTH_REQUIRED", True)
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)
    monkeypatch.setattr(A, "DATA_DIR", tmp_path)
    r = A.app.test_client().get("/login")
    assert r.status_code == 200
    assert b"/auth/google" not in r.data


def test_login_shows_google_when_configured(client):
    r = client.get("/login")
    assert r.status_code == 200
    assert b"/auth/google" in r.data
    body = r.get_data(as_text=True)
    assert "Google" in body


def test_google_link_is_outside_password_form(client):
    html = client.get("/login").get_data(as_text=True).lower()
    form_end = html.find("</form>")
    google_at = html.find("/auth/google")
    assert form_end != -1 and google_at != -1
    assert google_at > form_end


def test_google_start_rejects_unsafe_next(client, monkeypatch):
    monkeypatch.setattr(
        A,
        "google_authorize_redirect",
        lambda uri: A.redirect("https://accounts.google.com/o/oauth2/v2/auth"),
    )
    r = client.get("/auth/google?next=//evil.example")
    assert r.status_code == 302
    with client.session_transaction() as s:
        assert "login_next" not in s


def test_google_start_redirects_to_provider(client, monkeypatch):
    monkeypatch.setattr(
        A,
        "google_authorize_redirect",
        lambda uri: A.redirect("https://accounts.google.com/o/oauth2/v2/auth"),
    )
    r = client.get("/auth/google?next=/api/me")
    assert r.status_code == 302
    assert "accounts.google.com" in r.headers["Location"]
    with client.session_transaction() as s:
        assert s.get("login_next") == "/api/me"


def test_google_start_without_config(monkeypatch, tmp_path):
    monkeypatch.setattr(A, "AUTH_REQUIRED", True)
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)
    r = A.app.test_client().get("/auth/google")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "Google" in body


def test_google_callback_signs_up_and_logs_in(client, monkeypatch, google_env):
    monkeypatch.setattr(A, "google_authorize_access_token", lambda: _token())
    r = client.get("/auth/google/callback")
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/")
    with client.session_transaction() as s:
        assert s["user"] == "alice_at_school_ac_th"
        assert s["auth_provider"] == "google"
    assert (google_env / "oauth_users.json").is_file()


def test_google_callback_rejects_unverified_email(client, monkeypatch):
    monkeypatch.setattr(A, "google_authorize_access_token", lambda: _token(verified=False))
    r = client.get("/auth/google/callback")
    assert r.status_code == 200
    with client.session_transaction() as s:
        assert "user" not in s


def test_google_callback_rejects_domain(client, monkeypatch):
    monkeypatch.setenv("GOOGLE_ALLOWED_DOMAINS", "other.ac.th")
    monkeypatch.setattr(A, "google_authorize_access_token", lambda: _token())
    r = client.get("/auth/google/callback")
    assert r.status_code == 200
    with client.session_transaction() as s:
        assert "user" not in s


def test_google_signup_closed(client, monkeypatch):
    monkeypatch.setenv("GOOGLE_SIGNUP", "false")
    monkeypatch.setattr(A, "google_authorize_access_token", lambda: _token())
    r = client.get("/auth/google/callback")
    assert r.status_code == 200
    with client.session_transaction() as s:
        assert "user" not in s


def test_google_existing_user_when_signup_closed(client, monkeypatch, google_env):
    from oauth_core import upsert_google_user

    upsert_google_user(
        google_env,
        sub="gid-1",
        email="alice@school.ac.th",
        safe_name=A.safe_name,
    )
    monkeypatch.setenv("GOOGLE_SIGNUP", "false")
    monkeypatch.setattr(A, "google_authorize_access_token", lambda: _token())
    r = client.get("/auth/google/callback")
    assert r.status_code == 302
    with client.session_transaction() as s:
        assert s["user"] == "alice_at_school_ac_th"


def test_google_denied_query(client):
    r = client.get("/auth/google/callback?error=access_denied")
    assert r.status_code == 200
    with client.session_transaction() as s:
        assert "user" not in s


def test_school_mode_skips_google_routes():
    assert A.AUTH_REQUIRED is False
    c = A.app.test_client()
    r = c.get("/auth/google", follow_redirects=False)
    assert r.status_code == 302
