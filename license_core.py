"""ไลเซนต์ผูกเครื่อง — ใช้ offline หลังเปิดใช้แล้ว"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import platform
import re
import time
import uuid
from pathlib import Path
from typing import Any, Optional

# ดูแล 5 ปี (วัน)
DEFAULT_SUPPORT_DAYS = 1825
KEY_PREFIX = "PFM1"


def _license_secret() -> str:
    return os.environ.get("LICENSE_SECRET", "pdf-form-marker-dev-secret-change-me")


def get_machine_id() -> str:
    """รหัสเครื่องสั้นๆ สำหรับส่งให้ผู้ขายออกคีย์"""
    parts = [platform.node(), platform.system(), platform.machine(), str(uuid.getnode())]
    if platform.system() == "Windows":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Cryptography",
            ) as key:
                guid, _ = winreg.QueryValueEx(key, "MachineGuid")
                parts.append(str(guid))
        except OSError:
            pass
    else:
        for p in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
            try:
                parts.append(Path(p).read_text(encoding="utf-8").strip())
                break
            except OSError:
                continue
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest().upper()
    return digest[:16]


def _sign(machine_id: str, exp_yyyymmdd: str) -> str:
    msg = f"{KEY_PREFIX}|{machine_id.upper()}|{exp_yyyymmdd}"
    return hmac.new(
        _license_secret().encode("utf-8"),
        msg.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:12].upper()


def issue_license_key(machine_id: str, days: int = DEFAULT_SUPPORT_DAYS) -> str:
    """ออกคีย์จากรหัสเครื่อง (ใช้ฝั่งผู้ขาย)"""
    mid = re.sub(r"[^0-9A-Fa-f]", "", machine_id).upper()
    if len(mid) != 16:
        raise ValueError("รหัสเครื่องต้องเป็น 16 ตัวอักษรเลขฐานสิบหก")
    exp = time.strftime("%Y%m%d", time.localtime(time.time() + days * 86400))
    sig = _sign(mid, exp)
    raw = f"{KEY_PREFIX}-{mid}-{exp}-{sig}"
    return raw


def parse_and_verify_key(key: str, machine_id: Optional[str] = None) -> dict[str, Any]:
    """ตรวจคีย์ ถ้าผ่านคืน {machine_id, expires, days_left}"""
    cleaned = re.sub(r"\s+", "", (key or "").strip().upper())
    parts = cleaned.split("-")
    if len(parts) != 4 or parts[0] != KEY_PREFIX:
        raise ValueError("รูปแบบคีย์ไม่ถูกต้อง")
    mid, exp, sig = parts[1], parts[2], parts[3]
    if len(mid) != 16 or not re.fullmatch(r"[0-9A-F]{16}", mid):
        raise ValueError("รหัสเครื่องในคีย์ไม่ถูกต้อง")
    if not re.fullmatch(r"\d{8}", exp):
        raise ValueError("วันหมดอายุในคีย์ไม่ถูกต้อง")
    if not hmac.compare_digest(_sign(mid, exp), sig):
        raise ValueError("คีย์ไม่ถูกต้องหรือออกด้วยความลับคนละชุด")

    expect = (machine_id or get_machine_id()).upper()
    if mid != expect:
        raise ValueError("คีย์นี้ผูกกับเครื่องอื่น ไม่ใช้กับเครื่องนี้ได้")

    # หมดอายุสิ้นวัน exp (ท้องถิ่น)
    exp_struct = time.strptime(exp + "235959", "%Y%m%d%H%M%S")
    exp_ts = time.mktime(exp_struct)
    now = time.time()
    if now > exp_ts:
        raise ValueError("ไลเซนต์หมดอายุแล้ว")

    days_left = max(0, int((exp_ts - now) // 86400))
    return {
        "machine_id": mid,
        "expires": f"{exp[0:4]}-{exp[4:6]}-{exp[6:8]}",
        "expires_raw": exp,
        "days_left": days_left,
        "key": cleaned,
    }


def license_path(data_dir: Path) -> Path:
    return Path(data_dir) / "license.json"


def load_license_file(data_dir: Path) -> Optional[dict[str, Any]]:
    path = license_path(data_dir)
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def save_license_file(data_dir: Path, info: dict[str, Any]) -> None:
    path = license_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "key": info["key"],
        "machine_id": info["machine_id"],
        "expires": info["expires"],
        "activated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def license_status(data_dir: Path) -> dict[str, Any]:
    """สถานะไลเซนต์สำหรับ API/UI"""
    if os.environ.get("LICENSE_BYPASS", "").lower() in ("1", "true", "yes"):
        return {
            "licensed": True,
            "bypass": True,
            "machine_id": get_machine_id(),
            "expires": None,
            "days_left": None,
            "message": "โหมดพัฒนา (LICENSE_BYPASS)",
            "demo_only": False,
        }

    mid = get_machine_id()
    stored = load_license_file(data_dir)
    if not stored or not stored.get("key"):
        return {
            "licensed": False,
            "bypass": False,
            "machine_id": mid,
            "expires": None,
            "days_left": None,
            "message": "ยังไม่ได้เปิดใช้ไลเซนต์ — ทดลองสร้าง PDF ได้เฉพาะ demo-form.pdf",
            "demo_only": True,
        }

    try:
        info = parse_and_verify_key(stored["key"], mid)
        return {
            "licensed": True,
            "bypass": False,
            "machine_id": mid,
            "expires": info["expires"],
            "days_left": info["days_left"],
            "message": f"ไลเซนต์ใช้งานได้ถึง {info['expires']} (เหลือ ~{info['days_left']} วัน)",
            "demo_only": False,
        }
    except ValueError as e:
        return {
            "licensed": False,
            "bypass": False,
            "machine_id": mid,
            "expires": stored.get("expires"),
            "days_left": 0,
            "message": str(e),
            "demo_only": True,
        }


def can_fill_document(data_dir: Path, doc_name: str) -> tuple[bool, str]:
    """อนุญาตสร้าง PDF หรือไม่"""
    st = license_status(data_dir)
    if st["licensed"]:
        return True, ""
    base = Path(doc_name or "").name.lower()
    if base == "demo-form.pdf":
        return True, ""
    return (
        False,
        "ต้องมีไลเซนต์ถึงจะสร้าง PDF ของเอกสารนี้ได้ "
        f"(รหัสเครื่อง: {st['machine_id']}) — ทดลองได้เฉพาะ demo-form.pdf",
    )


def activate_license(data_dir: Path, key: str) -> dict[str, Any]:
    info = parse_and_verify_key(key, get_machine_id())
    save_license_file(data_dir, info)
    return license_status(data_dir)
