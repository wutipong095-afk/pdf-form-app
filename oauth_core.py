"""บัญชีที่สมัคร/เข้าด้วย Google OAuth — เก็บที่ DATA_DIR/oauth_users.json"""
from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Optional

from envutil import env_bool

STORE_FILE = "oauth_users.json"
STORE_VERSION = 1
MAX_FILE_BYTES = 2 * 1024 * 1024

_LOCK = Lock()


class _InterprocessLock:
    """ล็อกไฟล์ข้าม gunicorn worker — threading.Lock กันแค่ในโปรเซสเดียวกัน"""

    def __init__(self, path: Path):
        self.path = path
        self._fh = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.path, "a+b")
        try:
            if self._fh.tell() == 0:
                self._fh.write(b"\0")
                self._fh.flush()
            self._fh.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self._fh.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl

                fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX)
        except BaseException:
            self._fh.close()
            self._fh = None
            raise
        return self

    def __exit__(self, *exc: object) -> None:
        if self._fh is None:
            return
        try:
            self._fh.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        finally:
            self._fh.close()
            self._fh = None


def _store_lock(data_dir: Path) -> _InterprocessLock:
    return _InterprocessLock(Path(data_dir) / f".{STORE_FILE}.lock")


class OAuthUsersUnreadable(RuntimeError):
    """มีไฟล์บัญชี OAuth แต่อ่านไม่ได้ — ห้ามเขียนทับ"""


def google_configured() -> bool:
    return bool(
        os.environ.get("GOOGLE_CLIENT_ID", "").strip()
        and os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
    )


def google_oauth_enabled(auth_required: bool) -> bool:
    return bool(auth_required and google_configured())


def allowed_email_domains() -> list[str]:
    raw = os.environ.get("GOOGLE_ALLOWED_DOMAINS", "").strip()
    if not raw:
        return []
    return [part.strip().lower().lstrip("@") for part in raw.split(",") if part.strip()]


def email_domain_allowed(email: str) -> bool:
    domains = allowed_email_domains()
    if not domains:
        return True
    return email_domain(email) in domains


def email_domain(email: str) -> str:
    raw = email.strip().lower()
    if "@" not in raw:
        return ""
    return raw.rsplit("@", 1)[-1]


def email_is_verified(info: dict[str, Any]) -> bool:
    v = info.get("email_verified")
    if v is True:
        return True
    if isinstance(v, str) and v.strip().lower() in ("1", "true", "yes"):
        return True
    return False


def store_path(data_dir: Path) -> Path:
    return Path(data_dir) / STORE_FILE


def _empty() -> dict[str, Any]:
    return {"version": STORE_VERSION, "users": {}}


def load_oauth_users(data_dir: Path) -> dict[str, Any]:
    path = store_path(data_dir)
    if not path.is_file():
        return _empty()
    try:
        size = path.stat().st_size
        if size > MAX_FILE_BYTES:
            raise OAuthUsersUnreadable(f"{STORE_FILE} is too large ({size} bytes)")
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as e:
        raise OAuthUsersUnreadable(f"cannot read {STORE_FILE}: {e}") from e
    except ValueError as e:
        raise OAuthUsersUnreadable(f"{STORE_FILE} is not valid JSON: {e}") from e
    if not isinstance(data, dict):
        raise OAuthUsersUnreadable(f"{STORE_FILE} root is not an object")
    users = data.get("users")
    if users is None:
        users = {}
    if not isinstance(users, dict):
        raise OAuthUsersUnreadable(f"{STORE_FILE} has no users object")
    out: dict[str, Any] = {}
    for sub, rec in users.items():
        key = str(sub or "").strip()
        if not key or not isinstance(rec, dict):
            raise OAuthUsersUnreadable("oauth user entry is invalid")
        username = str(rec.get("username") or "").strip()
        email = str(rec.get("email") or "").strip().lower()
        if not username or not email:
            raise OAuthUsersUnreadable("oauth user missing username or email")
        out[key] = {
            "username": username,
            "email": email,
            "name": str(rec.get("name") or "").strip(),
            "created_at": str(rec.get("created_at") or ""),
        }
    return {"version": STORE_VERSION, "users": out}


def save_oauth_users(data_dir: Path, data: dict[str, Any]) -> None:
    path = store_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        {"version": STORE_VERSION, "users": data.get("users") or {}},
        ensure_ascii=False,
        indent=2,
    ) + "\n"
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".oauth-users-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def username_from_email(email: str, safe_name: Callable[[str], str]) -> str:
    base = safe_name(email.strip().lower().replace("@", "_at_"))
    base = re.sub(r"_+", "_", base).strip("._-")
    return base or "google_user"


def _unique_username(
    wanted: str,
    taken: set[str],
    sub: str,
    safe_name: Callable[[str], str],
) -> str:
    if wanted not in taken:
        return wanted
    suffix = safe_name(sub)[-8:] or "user"
    candidate = f"{wanted}_{suffix}"[:80]
    if candidate not in taken:
        return candidate
    n = 2
    while True:
        extra = f"{wanted}_{suffix}_{n}"[:80]
        if extra not in taken:
            return extra
        n += 1


def find_google_username(data_dir: Path, sub: str) -> Optional[str]:
    rec = load_oauth_users(data_dir)["users"].get(str(sub or "").strip())
    if not rec:
        return None
    return str(rec.get("username") or "") or None


def upsert_google_user(
    data_dir: Path,
    *,
    sub: str,
    email: str,
    display_name: str = "",
    reserved: Optional[set[str]] = None,
    safe_name: Callable[[str], str],
) -> str:
    """สร้างบัญชีครั้งแรก (สมัคร) หรือคืน username เดิม — คืนชื่อที่ใช้เป็น session/โฟลเดอร์"""
    sub = str(sub or "").strip()
    email = str(email or "").strip().lower()
    if not sub or not email or "@" not in email:
        raise ValueError("google account is missing sub or email")

    with _LOCK, _store_lock(data_dir):
        store = load_oauth_users(data_dir)
        users: dict[str, Any] = store["users"]
        existing = users.get(sub)
        if existing:
            existing["email"] = email
            if display_name:
                existing["name"] = display_name.strip()[:120]
            save_oauth_users(data_dir, store)
            return str(existing["username"])

        taken = {str(rec.get("username") or "") for rec in users.values()}
        taken.update(reserved or set())
        wanted = username_from_email(email, safe_name)
        username = _unique_username(wanted, taken, sub, safe_name)
        users[sub] = {
            "username": username,
            "email": email,
            "name": (display_name or "").strip()[:120],
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        save_oauth_users(data_dir, store)
        return username


def parse_google_userinfo(token: Any) -> dict[str, str]:
    """ดึง sub / email / name จาก token ที่ Authlib คืนหลัง authorize_access_token"""
    info: dict[str, Any] = {}
    if isinstance(token, dict):
        raw = token.get("userinfo")
        if isinstance(raw, dict):
            info = raw
    email = str(info.get("email") or "").strip().lower()
    sub = str(info.get("sub") or "").strip()
    name = str(info.get("name") or "").strip()
    return {
        "sub": sub,
        "email": email,
        "name": name,
        "verified": "1" if email_is_verified(info) else "",
    }


def google_signup_allowed() -> bool:
    """ค่าเริ่มต้นอนุญาตสมัครอัตโนมัติเมื่อ login Google ครั้งแรก — ปิดด้วย GOOGLE_SIGNUP=false"""
    return env_bool("GOOGLE_SIGNUP", True)


def google_public_signup_allowed() -> bool:
    """บนเน็ตต้องมี allowlist เว้นแต่ตั้ง GOOGLE_ALLOW_PUBLIC=true"""
    return env_bool("GOOGLE_ALLOW_PUBLIC", False)


def safe_login_next(raw: Any, fallback: str = "/") -> str:
    """อนุญาตแค่ path ในแอป — กัน open redirect และวน /login /auth"""
    if not isinstance(raw, str):
        return fallback
    nxt = raw.strip()
    if not nxt.startswith("/") or nxt.startswith("//"):
        return fallback
    if any(ch in nxt for ch in ("\\", "\n", "\r", "\0", "@")):
        return fallback
    if "//" in nxt or ":" in nxt:
        return fallback
    path = nxt.split("?", 1)[0].split("#", 1)[0]
    if path.startswith("/auth/") or path.rstrip("/") in ("/login", "/logout"):
        return fallback
    return nxt
