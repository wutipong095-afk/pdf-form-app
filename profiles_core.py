"""สมุดข้อมูลล่วงหน้า (autofill profiles) — คู่ ชื่อฟิลด์ → ค่า ใช้ซ้ำข้ามฟอร์ม

เก็บไฟล์เดียวที่ user_root/profiles.json ไม่ผูกกับ PDF และไม่มีพิกัด
จับคู่ตอนใช้งานด้วยชื่อฟิลด์แบบตรงตัว (exact match) เท่านั้น — ฝั่ง client เป็นคนเติมค่า
"""
from __future__ import annotations

import json
import os
import secrets
import tempfile
from pathlib import Path
from typing import Any

from i18n_core import t

PROFILES_FILE = "profiles.json"
PROFILES_VERSION = 1
KINDS = ("org", "partner", "person")
DEFAULT_KIND = "org"

MAX_PROFILES = 50
MAX_NAME_LEN = 120
MAX_KEYS = 60
MAX_KEY_LEN = 80
MAX_VALUE_LEN = 500
# ต้องสูงกว่าไฟล์ที่ผ่าน validate ได้จริง ไม่งั้นสมุดที่ถูกต้องกลายเป็น "อ่านไม่ได้"
# worst case ≈ 50 โปรไฟล์ × 60 คู่ × (คีย์ 80 + ค่า 500 ตัวอักษร) × 4 ไบต์/ตัว ≈ 7MB
MAX_FILE_BYTES = 16 * 1024 * 1024


class ProfilesUnreadable(RuntimeError):
    """มีไฟล์สมุดอยู่แต่อ่านไม่ได้ — ห้ามเขียนทับ ไม่งั้นข้อมูลผู้ใช้หายทั้งก้อน"""


def profiles_path(user_root: Path) -> Path:
    return Path(user_root) / PROFILES_FILE


def new_profile_id() -> str:
    return "p-" + secrets.token_hex(4)


def _empty() -> dict[str, Any]:
    return {"version": PROFILES_VERSION, "profiles": []}


def _read_profile(raw: Any) -> dict[str, Any]:
    """อ่านหนึ่งโปรไฟล์จากไฟล์ — เพี้ยนเมื่อไหร่โยน ไม่เงียบแล้วทิ้ง"""
    if not isinstance(raw, dict):
        raise ProfilesUnreadable("profile entry is not an object")
    pid = str(raw.get("id") or "").strip()
    name = str(raw.get("name") or "").strip()
    if not pid or not name:
        raise ProfilesUnreadable("profile entry has no id or name")
    kind = str(raw.get("kind") or DEFAULT_KIND).strip()
    if kind not in KINDS:
        kind = DEFAULT_KIND
    raw_values = raw.get("values") or {}
    if not isinstance(raw_values, dict):
        raise ProfilesUnreadable("profile values is not an object")
    values: dict[str, str] = {}
    for k, v in raw_values.items():
        if not isinstance(k, str) or not isinstance(v, (str, int, float)):
            raise ProfilesUnreadable("profile values holds a non-text pair")
        key = k.strip()
        # คีย์ว่าง หรือคีย์ที่ trim แล้วชนกัน = ทิ้งค่าเงียบ ๆ แล้วค่าหายตอนเซฟรอบถัดไป
        if not key:
            raise ProfilesUnreadable("profile has an empty field name")
        if key in values:
            raise ProfilesUnreadable(f"profile has two field names that trim to {key!r}")
        values[key] = str(v)
    return {"id": pid, "name": name[:MAX_NAME_LEN], "kind": kind, "values": values}


def load_profiles(user_root: Path) -> dict[str, Any]:
    """คืนสมุดจากไฟล์ — ไฟล์ไม่มี = สมุดว่าง, ไฟล์มีแต่อ่านไม่ได้ = โยน ProfilesUnreadable

    ห้ามคืนสมุดว่างเมื่อไฟล์เสีย เพราะ caller จะเซฟทับแล้วข้อมูลเดิมหายหมด
    """
    path = profiles_path(user_root)
    if not path.is_file():
        return _empty()
    try:
        size = path.stat().st_size
        if size > MAX_FILE_BYTES:
            raise ProfilesUnreadable(f"profiles.json is too large ({size} bytes)")
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as e:
        raise ProfilesUnreadable(f"cannot read profiles.json: {e}") from e
    except ValueError as e:
        raise ProfilesUnreadable(f"profiles.json is not valid JSON: {e}") from e
    if not isinstance(data, dict):
        raise ProfilesUnreadable("profiles.json root is not an object")
    entries = data.get("profiles")
    if entries is None:
        entries = []
    if not isinstance(entries, list):
        raise ProfilesUnreadable("profiles.json has no profile list")
    out = []
    seen: set[str] = set()
    for raw in entries:
        p = _read_profile(raw)
        if p["id"] in seen:
            raise ProfilesUnreadable(f"duplicate profile id {p['id']}")
        seen.add(p["id"])
        out.append(p)
    # ไม่ตัดที่ MAX_PROFILES ตอนอ่าน — ตัดแล้วเซฟทับคือข้อมูลหาย (create_profile กันจำนวนอยู่แล้ว)
    return {"version": PROFILES_VERSION, "profiles": out}


def save_profiles(user_root: Path, data: dict[str, Any]) -> None:
    """เขียนแบบ atomic — temp ในโฟลเดอร์เดียวกันแล้ว os.replace"""
    path = profiles_path(user_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        {"version": PROFILES_VERSION, "profiles": data.get("profiles") or []},
        ensure_ascii=False,
        indent=2,
    ) + "\n"
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".profiles-", suffix=".tmp")
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


def validate_payload(raw: Any) -> tuple[str, str, dict[str, str]]:
    """ตรวจ body จาก client — คืน (name, kind, values) หรือโยน ValueError"""
    if not isinstance(raw, dict):
        raise ValueError(t("profiles.badPayload"))

    name = str(raw.get("name") or "").strip()
    if not name:
        raise ValueError(t("profiles.needName"))
    if len(name) > MAX_NAME_LEN:
        raise ValueError(t("profiles.nameTooLong", max=MAX_NAME_LEN))

    kind = str(raw.get("kind") or DEFAULT_KIND).strip()
    if kind not in KINDS:
        raise ValueError(t("profiles.badKind"))

    values_raw = raw.get("values")
    if values_raw is None:
        values_raw = {}
    if not isinstance(values_raw, dict):
        raise ValueError(t("profiles.badValues"))
    if len(values_raw) > MAX_KEYS:
        raise ValueError(t("profiles.tooManyKeys", max=MAX_KEYS))

    values: dict[str, str] = {}
    for k, v in values_raw.items():
        if not isinstance(k, str):
            raise ValueError(t("profiles.badValues"))
        key = k.strip()
        if not key:
            raise ValueError(t("profiles.emptyKey"))
        # i18n_core.t() takes `key` positionally — placeholders here use {name}
        if len(key) > MAX_KEY_LEN:
            raise ValueError(t("profiles.keyTooLong", name=key[:20], max=MAX_KEY_LEN))
        if key in values:
            raise ValueError(t("profiles.duplicateKey", name=key))
        if v is None:
            v = ""
        if not isinstance(v, (str, int, float)):
            raise ValueError(t("profiles.badValues"))
        text = str(v)
        if len(text) > MAX_VALUE_LEN:
            raise ValueError(t("profiles.valueTooLong", name=key, max=MAX_VALUE_LEN))
        values[key] = text
    return name, kind, values


def create_profile(user_root: Path, raw: Any) -> dict[str, Any]:
    name, kind, values = validate_payload(raw)
    data = load_profiles(user_root)
    if len(data["profiles"]) >= MAX_PROFILES:
        raise ValueError(t("profiles.tooMany", max=MAX_PROFILES))
    used = {p["id"] for p in data["profiles"]}
    pid = new_profile_id()
    while pid in used:
        pid = new_profile_id()
    profile = {"id": pid, "name": name, "kind": kind, "values": values}
    data["profiles"].append(profile)
    save_profiles(user_root, data)
    return profile


def update_profile(user_root: Path, profile_id: str, raw: Any) -> dict[str, Any]:
    name, kind, values = validate_payload(raw)
    data = load_profiles(user_root)
    for p in data["profiles"]:
        if p["id"] == profile_id:
            p["name"] = name
            p["kind"] = kind
            p["values"] = values
            save_profiles(user_root, data)
            return p
    raise KeyError(profile_id)


def delete_profile(user_root: Path, profile_id: str) -> None:
    data = load_profiles(user_root)
    rest = [p for p in data["profiles"] if p["id"] != profile_id]
    if len(rest) == len(data["profiles"]):
        raise KeyError(profile_id)
    data["profiles"] = rest
    save_profiles(user_root, data)
