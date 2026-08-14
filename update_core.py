"""ตรวจเวอร์ชันอัปเดตจาก latest.json บนเน็ต — ล้มเหลวแล้วเงียบ ไม่บังคับออนไลน์"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

from envutil import APP_VERSION, BASE, app_root_dir


_CACHE: dict[str, Any] = {"checked_at": 0.0, "payload": None}
_CACHE_TTL_S = 6 * 3600
_FETCH_TIMEOUT_S = 3.0
_DOWNLOAD_TIMEOUT_S = 180.0
_MAX_SETUP_BYTES = 200 * 1024 * 1024
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SETUP_NAME_RE = re.compile(
    r"^(?:FromDD|PDFFormMarker)-Setup-(\d+\.\d+\.\d+(?:\.\d+)?)\.exe$",
    re.IGNORECASE,
)
_UA = f"FromDD/{APP_VERSION}"


class UpdateInstallError(Exception):
    """ดาวน์โหลด/ตรวจตัวติดตั้งไม่ผ่าน — `code` ไป map เป็นข้อความในแอป"""

    def __init__(self, code: str, detail: str = ""):
        self.code = code
        self.detail = detail
        super().__init__(detail or code)


class _HttpsOnlyRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urlparse(newurl)
        if parsed.scheme and parsed.scheme != "https":
            raise urllib.error.URLError("redirect must stay on https")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def parse_version(v: str) -> tuple[int, ...]:
    """แปลง 0.1.8 / v0.1.8 → tuple เทียบได้"""
    s = (v or "").strip().lstrip("vV")
    parts: list[int] = []
    for p in s.split("."):
        num = ""
        for ch in p:
            if ch.isdigit():
                num += ch
            else:
                break
        parts.append(int(num) if num else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:4])


def is_newer(latest: str, current: str) -> bool:
    return parse_version(latest) > parse_version(current)


def _safe_update_url(value: str) -> str:
    url = (value or "").strip()
    try:
        parsed = urlparse(url)
    except ValueError:
        return ""
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        return ""
    return url


def normalize_sha256(value: Any) -> str:
    s = str(value or "").strip().lower().replace(" ", "")
    if s.startswith("sha256:"):
        s = s[7:]
    if not _SHA256_RE.fullmatch(s):
        return ""
    return s


def parse_size(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    if n <= 0 or n > _MAX_SETUP_BYTES:
        return None
    return n


def setup_filename_from_url(url: str) -> str:
    name = Path(urlparse(url).path).name
    if not _SETUP_NAME_RE.fullmatch(name):
        return ""
    return name


def filename_matches_version(filename: str, version: str) -> bool:
    m = _SETUP_NAME_RE.fullmatch(filename or "")
    if not m:
        return False
    feed_ver = (version or "").strip().lstrip("vV")
    return m.group(1) == feed_ver


def resolve_update_feed_url() -> str:
    """ลำดับ: UPDATE_CHECK_URL env → AppData/update_feed.url → ข้าง exe/update_feed.url"""
    env = (os.environ.get("UPDATE_CHECK_URL") or "").strip()
    if env:
        return _safe_update_url(env)
    candidates = [
        app_root_dir() / "update_feed.url",
        BASE / "update_feed.url",
    ]
    # frozen onedir: exe parent อาจต่างจาก _MEIPASS
    if getattr(__import__("sys"), "frozen", False):
        import sys

        exe_dir = Path(sys.executable).resolve().parent
        candidates.insert(0, exe_dir / "update_feed.url")
        candidates.insert(1, exe_dir / "_internal" / "update_feed.url")
    for p in candidates:
        try:
            if p.is_file():
                url = p.read_text(encoding="utf-8").strip().splitlines()[0].strip()
                if url and not url.startswith("#"):
                    return _safe_update_url(url)
        except OSError:
            continue
    return ""


def _https_opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(_HttpsOnlyRedirect)


def _fetch_latest(url: str) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": _UA,
            "Accept": "application/json",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
        method="GET",
    )
    with _https_opener().open(req, timeout=_FETCH_TIMEOUT_S) as resp:
        raw = resp.read(64_000)
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("latest.json ต้องเป็น object")
    return data


def check_for_update(*, force: bool = False, current: Optional[str] = None) -> dict[str, Any]:
    """คืนสถานะอัปเดต — ไม่โยน exception ออกนอก (แอปใช้ต่อได้เสมอ)"""
    cur = (current or APP_VERSION).strip()
    feed = resolve_update_feed_url()
    base: dict[str, Any] = {
        "current": cur,
        "update_available": False,
        "disabled": not bool(feed),
        "offline": False,
        "latest": None,
        "setup_url": None,
        "sha256": None,
        "size": None,
        "notes": None,
        "published_at": None,
        "feed_url": feed or None,
    }
    if not feed:
        return base

    now = time.time()
    if (
        not force
        and _CACHE.get("payload") is not None
        and now - float(_CACHE.get("checked_at") or 0) < _CACHE_TTL_S
    ):
        cached = dict(_CACHE["payload"])
        cached["cached"] = True
        return cached

    try:
        data = _fetch_latest(feed)
        latest = str(data.get("version") or data.get("latest") or "").strip()
        setup_url = _safe_update_url(str(data.get("setup_url") or data.get("url") or ""))
        notes = data.get("notes")
        published = data.get("published_at") or data.get("date")
        digest = normalize_sha256(data.get("sha256") or data.get("sha256sum"))
        size = parse_size(data.get("size"))
        available = bool(latest and is_newer(latest, cur))
        result = {
            "current": cur,
            "update_available": available,
            "disabled": False,
            "offline": False,
            "latest": latest or None,
            "setup_url": setup_url or None,
            "sha256": digest or None,
            "size": size,
            "notes": (str(notes).strip() if notes else None),
            "published_at": (str(published).strip() if published else None),
            "feed_url": feed,
            "cached": False,
        }
        _CACHE["checked_at"] = now
        _CACHE["payload"] = result
        return result
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, OSError):
        base["offline"] = True
        return base


def download_and_verify_setup(dest_dir: Path, *, force: bool = True) -> dict[str, Any]:
    """ดาวน์โหลด Setup จาก latest.json แล้วตรวจ SHA-256 ก่อนคืน path

    ไม่รันไฟล์ — ผู้เรียกเป็นคนเปิดหลังผู้ใช้กดปุ่ม
    """
    info = check_for_update(force=force)
    if info.get("disabled") or not info.get("feed_url"):
        raise UpdateInstallError("no_feed")
    if info.get("offline"):
        raise UpdateInstallError("offline")
    if not info.get("update_available"):
        raise UpdateInstallError("no_update")

    setup_url = str(info.get("setup_url") or "")
    latest = str(info.get("latest") or "")
    digest = normalize_sha256(info.get("sha256"))
    expected_size = parse_size(info.get("size"))
    filename = setup_filename_from_url(setup_url)

    if not setup_url:
        raise UpdateInstallError("no_setup_url")
    if not digest:
        raise UpdateInstallError("no_sha256")
    if not filename or not filename_matches_version(filename, latest):
        raise UpdateInstallError("bad_filename")

    dest_dir = dest_dir.resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename
    part = dest.with_name(filename + ".part")

    if dest.is_file():
        existing = hashlib.sha256(dest.read_bytes()).hexdigest()
        if existing == digest and (expected_size is None or dest.stat().st_size == expected_size):
            return {
                "ok": True,
                "path": str(dest),
                "sha256": digest,
                "size": dest.stat().st_size,
                "version": latest,
                "filename": filename,
                "reused": True,
            }

    req = urllib.request.Request(
        setup_url,
        headers={"User-Agent": _UA, "Accept": "application/octet-stream"},
        method="GET",
    )
    hasher = hashlib.sha256()
    total = 0
    try:
        if part.exists():
            part.unlink()
        with _https_opener().open(req, timeout=_DOWNLOAD_TIMEOUT_S) as resp:
            length_hdr = resp.headers.get("Content-Length")
            if length_hdr:
                try:
                    declared = int(length_hdr)
                except ValueError:
                    declared = -1
                if declared > _MAX_SETUP_BYTES:
                    raise UpdateInstallError("too_large")
                if expected_size is not None and declared != expected_size:
                    raise UpdateInstallError("size_mismatch")
            with part.open("wb") as out:
                while True:
                    chunk = resp.read(1024 * 256)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > _MAX_SETUP_BYTES:
                        raise UpdateInstallError("too_large")
                    hasher.update(chunk)
                    out.write(chunk)
    except UpdateInstallError:
        _unlink_quiet(part)
        raise
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
        _unlink_quiet(part)
        raise UpdateInstallError("download_fail", str(exc)) from exc

    if expected_size is not None and total != expected_size:
        _unlink_quiet(part)
        raise UpdateInstallError("size_mismatch")

    got = hasher.hexdigest()
    if got != digest:
        _unlink_quiet(part)
        raise UpdateInstallError("hash_mismatch")

    try:
        part.replace(dest)
    except OSError as exc:
        _unlink_quiet(part)
        raise UpdateInstallError("download_fail", str(exc)) from exc

    return {
        "ok": True,
        "path": str(dest),
        "sha256": got,
        "size": total,
        "version": latest,
        "filename": filename,
        "reused": False,
    }


def _unlink_quiet(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
    except OSError:
        pass
