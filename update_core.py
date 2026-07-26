"""ตรวจเวอร์ชันอัปเดตจาก latest.json บนเน็ต — ล้มเหลวแล้วเงียบ ไม่บังคับออนไลน์"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional

from envutil import APP_VERSION, BASE, app_root_dir


_CACHE: dict[str, Any] = {"checked_at": 0.0, "payload": None}
_CACHE_TTL_S = 6 * 3600
_FETCH_TIMEOUT_S = 3.0


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


def resolve_update_feed_url() -> str:
    """ลำดับ: UPDATE_CHECK_URL env → AppData/update_feed.url → ข้าง exe/update_feed.url"""
    env = (os.environ.get("UPDATE_CHECK_URL") or "").strip()
    if env:
        return env
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
                    return url
        except OSError:
            continue
    return ""


def _fetch_latest(url: str) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": f"PDFFormMarker/{APP_VERSION}", "Accept": "application/json"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=_FETCH_TIMEOUT_S) as resp:
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
        setup_url = str(data.get("setup_url") or data.get("url") or "").strip()
        notes = data.get("notes")
        published = data.get("published_at") or data.get("date")
        available = bool(latest and is_newer(latest, cur))
        result = {
            "current": cur,
            "update_available": available,
            "disabled": False,
            "offline": False,
            "latest": latest or None,
            "setup_url": setup_url or None,
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
