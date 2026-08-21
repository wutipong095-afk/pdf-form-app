"""บัญชี Google OAuth — เก็บไฟล์, โดเมนอีเมล, ตั้งชื่อ user"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from oauth_core import (  # noqa: E402
    OAuthUsersUnreadable,
    email_domain,
    email_domain_allowed,
    email_is_verified,
    find_google_username,
    google_configured,
    google_oauth_enabled,
    load_oauth_users,
    parse_google_userinfo,
    safe_login_next,
    store_path,
    upsert_google_user,
    username_from_email,
)


def safe(name: str) -> str:
    return re.sub(r"[^\w\-ก-๙]", "_", name or "")


def test_username_from_email_is_filesystem_safe():
    assert username_from_email("alice@school.ac.th", safe) == "alice_at_school_ac_th"


def test_upsert_creates_then_returns_same_user(tmp_path: Path):
    u1 = upsert_google_user(
        tmp_path, sub="sub-1", email="alice@school.ac.th", display_name="Alice", safe_name=safe
    )
    u2 = upsert_google_user(
        tmp_path, sub="sub-1", email="alice@school.ac.th", display_name="Alice B", safe_name=safe
    )
    assert u1 == u2
    rec = load_oauth_users(tmp_path)["users"]["sub-1"]
    assert rec["username"] == u1
    assert rec["name"] == "Alice B"


def test_upsert_avoids_reserved_and_colliding_names(tmp_path: Path):
    first = upsert_google_user(
        tmp_path, sub="aaa", email="bob@school.ac.th", reserved={"bob_at_school_ac_th"}, safe_name=safe
    )
    assert first != "bob_at_school_ac_th"
    second = upsert_google_user(
        tmp_path, sub="bbb", email="bob@school.ac.th", reserved=set(), safe_name=safe
    )
    assert second != first


def test_damaged_store_raises(tmp_path: Path):
    store_path(tmp_path).write_text("{ not json", encoding="utf-8")
    with pytest.raises(OAuthUsersUnreadable):
        load_oauth_users(tmp_path)


def test_email_domain_allowlist(monkeypatch):
    monkeypatch.delenv("GOOGLE_ALLOWED_DOMAINS", raising=False)
    assert email_domain_allowed("anyone@gmail.com")
    monkeypatch.setenv("GOOGLE_ALLOWED_DOMAINS", "school.ac.th, other.ac.th")
    assert email_domain_allowed("a@school.ac.th")
    assert not email_domain_allowed("a@gmail.com")


def test_email_verified_and_userinfo_parse():
    assert email_is_verified({"email_verified": True})
    assert email_is_verified({"email_verified": "true"})
    assert not email_is_verified({"email_verified": False})
    info = parse_google_userinfo({
        "userinfo": {
            "sub": "99",
            "email": "A@School.ac.th",
            "email_verified": True,
            "name": "Ann",
        }
    })
    assert info["email"] == "a@school.ac.th"
    assert info["sub"] == "99"
    assert info["verified"] == "1"


def test_google_configured_needs_both(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)
    assert not google_configured()
    assert not google_oauth_enabled(True)
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret")
    assert google_configured()
    assert google_oauth_enabled(True)
    assert not google_oauth_enabled(False)


def test_find_missing_user(tmp_path: Path):
    assert find_google_username(tmp_path, "nope") is None
    upsert_google_user(tmp_path, sub="s", email="a@b.c", safe_name=safe)
    assert find_google_username(tmp_path, "s") == username_from_email("a@b.c", safe)


def test_safe_login_next_rejects_open_redirects():
    assert safe_login_next("/api/me") == "/api/me"
    assert safe_login_next("/") == "/"
    assert safe_login_next("//evil.example") == "/"
    assert safe_login_next("/\\evil.example") == "/"
    assert safe_login_next("/auth/google") == "/"
    assert safe_login_next("/login") == "/"
    assert safe_login_next("https://evil.example/") == "/"
    assert safe_login_next("/foo@bar") == "/"


def test_email_domain_helper():
    assert email_domain("a@School.ac.th") == "school.ac.th"
    assert email_domain("nope") == ""


def test_atomic_save_leaves_no_temp(tmp_path: Path):
    upsert_google_user(tmp_path, sub="s", email="a@b.c", safe_name=safe)
    leftovers = [
        p.name
        for p in tmp_path.iterdir()
        if p.name.startswith(".oauth-users-")
    ]
    assert leftovers == []
    data = json.loads(store_path(tmp_path).read_text(encoding="utf-8"))
    assert "s" in data["users"]
