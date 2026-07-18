"""ไลเซนต์ผูกเครื่อง — ตรวจด้วย Ed25519 (แอปมีแค่ public key)

ข้อผิดพลาดสองช่องทาง:
  ValueError  = คีย์/สถานะไลเซนต์มีปัญหา (โชว์ผู้ใช้ได้)
  RuntimeError = แอปตั้งค่าผิดฝั่งเซิร์ฟเวอร์ (public key หาย, ไฟล์รหัสเครื่องเสีย, demo ต้นฉบับหาย)
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from envutil import BASE, env_bool

DEFAULT_SUPPORT_DAYS = 1825
KEY_PREFIX = "PFM2"
DEMO_DOC_NAME = "demo-form.pdf"
CANONICAL_DEMO_PATH = BASE / "demo" / "uploads" / DEMO_DOC_NAME
DEFAULT_PUBLIC_KEY_PATH = BASE / "license_public.pem"
DEFAULT_PRIVATE_KEY_PATH = BASE / "keys" / "ed25519_private.pem"
# ยอมให้นาฬิกาย้อนได้ไม่เกินนี้ (วินาที) ก่อนถือว่าน่าสงสัย
CLOCK_ROLLBACK_GRACE = 86400
# เขียน clock_guard เมื่อเวลาเดินหน้าเกินช่วงนี้ — ไม่เขียนดิสก์ทุก request
CLOCK_WRITE_INTERVAL = 3600
# รอเนื้อหา machine_id ตอน cold-start / race
_MACHINE_ID_WAIT_TRIES = 20
_MACHINE_ID_WAIT_SLEEP = 0.05


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    _atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


_sha_cache: dict[str, tuple[int, int, str]] = {}


def file_sha256(path: Path) -> str:
    st = os.stat(path)
    key = str(path)
    hit = _sha_cache.get(key)
    if hit and hit[0] == st.st_mtime_ns and hit[1] == st.st_size:
        return hit[2]
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    digest = h.hexdigest()
    _sha_cache[key] = (st.st_mtime_ns, st.st_size, digest)
    return digest


def canonical_demo_sha256() -> str:
    """hash ของ demo ที่ ship มากับแอป — ไม่ cache แยกจาก file_sha256 (mtime)"""
    if not CANONICAL_DEMO_PATH.is_file():
        raise RuntimeError(
            f"ไม่พบไฟล์ demo ต้นฉบับในแอป: {CANONICAL_DEMO_PATH} — ติดตั้ง/แพ็กเกจไม่ครบ"
        )
    return file_sha256(CANONICAL_DEMO_PATH)


def is_canonical_demo_pdf(path: Path) -> bool:
    """True ถ้าเนื้อหาตรง demo ทางการ; RuntimeError ถ้าต้นฉบับในแอปหาย"""
    canon = canonical_demo_sha256()
    try:
        return path.is_file() and file_sha256(path) == canon
    except OSError:
        return False


@lru_cache(maxsize=1)
def load_public_key() -> Ed25519PublicKey:
    pem_path = Path(os.environ.get("LICENSE_PUBLIC_KEY_PATH", DEFAULT_PUBLIC_KEY_PATH))
    if not pem_path.is_file():
        raise RuntimeError(f"ไม่พบ public key ไลเซนต์: {pem_path}")
    try:
        key = serialization.load_pem_public_key(pem_path.read_bytes())
    except (ValueError, OSError) as e:
        raise RuntimeError(f"public key ไลเซนต์เสียหายหรืออ่านไม่ได้: {pem_path}") from e
    if not isinstance(key, Ed25519PublicKey):
        raise RuntimeError("LICENSE public key ต้องเป็น Ed25519")
    return key


def private_key_path() -> Path:
    return Path(os.environ.get("LICENSE_PRIVATE_KEY_PATH", DEFAULT_PRIVATE_KEY_PATH))


def public_key_path() -> Path:
    return Path(os.environ.get("LICENSE_PUBLIC_KEY_PATH", DEFAULT_PUBLIC_KEY_PATH))


def load_private_key(path: Optional[Path] = None) -> Ed25519PrivateKey:
    """ฝั่งผู้ขายเท่านั้น — ห้ามใส่ใน image ลูกค้า"""
    pem_path = path or private_key_path()
    if not pem_path.is_file():
        raise RuntimeError(
            f"ไม่พบ private key: {pem_path} — รัน python scripts/gen_keypair.py ก่อน"
        )
    try:
        key = serialization.load_pem_private_key(pem_path.read_bytes(), password=None)
    except (ValueError, OSError) as e:
        raise RuntimeError(f"private key เสียหายหรืออ่านไม่ได้: {pem_path}") from e
    if not isinstance(key, Ed25519PrivateKey):
        raise RuntimeError("LICENSE private key ต้องเป็น Ed25519")
    return key


def machine_id_path(data_dir: Path) -> Path:
    return Path(data_dir) / "machine_id"


def _read_machine_id(path: Path) -> Optional[str]:
    try:
        raw = path.read_text(encoding="utf-8").strip().upper()
    except OSError:
        return None
    return raw if re.fullmatch(r"[0-9A-F]{16}", raw) else None


def _wait_machine_id(path: Path) -> Optional[str]:
    """รอเนื้อหาหลัง race สร้างไฟล์ — แยกจากกรณีไฟล์เสียจริง"""
    for _ in range(_MACHINE_ID_WAIT_TRIES):
        mid = _read_machine_id(path)
        if mid:
            return mid
        try:
            if path.stat().st_size > 0:
                # มีเนื้อหาแต่ไม่ใช่รหัส 16 hex — ไม่ใช่แค่เขียนไม่ทัน
                return None
        except OSError:
            return None
        time.sleep(_MACHINE_ID_WAIT_SLEEP)
    return _read_machine_id(path)


def get_machine_id(data_dir: str) -> str:
    """รหัสเครื่องถาวรบน volume/data — ไม่ผูก hostname ของ container

    ห้าม cache ข้าม request: ผู้ใช้ลบ data/machine_id ตามคู่มือกู้แล้ว
    ต้องได้รหัสใหม่ที่เขียนลงดิสก์ทันที ไม่ใช่รหัสเก่าค้างใน process"""
    path = machine_id_path(Path(data_dir))
    if path.is_file():
        mid = _wait_machine_id(path)
        if mid:
            return mid
        try:
            size = path.stat().st_size
        except OSError:
            size = -1
        if size == 0:
            raise RuntimeError(f"อ่านไฟล์รหัสเครื่อง {path} ไม่สำเร็จ (ไฟล์ว่างระหว่างเริ่มระบบ)")
        raise RuntimeError(
            f"ไฟล์รหัสเครื่อง {path} เสียหาย — กู้จากสำรอง หรือลบไฟล์เพื่อออกรหัสใหม่ "
            "(รหัสใหม่ต้องขอคีย์ใหม่จากผู้ขาย)"
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    mid = uuid.uuid4().hex[:16].upper()
    try:
        fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        existing = _wait_machine_id(path)
        if existing:
            return existing
        raise RuntimeError(f"อ่านไฟล์รหัสเครื่อง {path} ไม่สำเร็จ")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(mid + "\n")
    return mid


def _payload(machine_id: str, exp_yyyymmdd: str) -> bytes:
    return f"{KEY_PREFIX}|{machine_id.upper()}|{exp_yyyymmdd}".encode("utf-8")


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def issue_license_key(
    machine_id: str,
    days: int = DEFAULT_SUPPORT_DAYS,
    private_key: Optional[Ed25519PrivateKey] = None,
) -> str:
    mid = machine_id.strip().upper()
    if not re.fullmatch(r"[0-9A-F]{16}", mid):
        raise ValueError("รหัสเครื่องต้องเป็น 16 ตัวอักษรเลขฐานสิบหก")
    exp_dt = datetime.now(timezone.utc) + timedelta(days=days)
    exp = exp_dt.strftime("%Y%m%d")
    priv = private_key or load_private_key()
    sig = _b64url(priv.sign(_payload(mid, exp)))
    return f"{KEY_PREFIX}.{mid}.{exp}.{sig}"


def parse_and_verify_key(
    key: str, machine_id: str, now: Optional[datetime] = None
) -> dict[str, Any]:
    cleaned = re.sub(r"\s+", "", (key or "").strip())
    if cleaned.upper().startswith("PFM1-") or cleaned.upper().startswith("PFM1."):
        raise ValueError("คีย์รุ่นเก่า (PFM1) ใช้กับเวอร์ชันนี้ไม่ได้ — ติดต่อผู้ขายเพื่อออกคีย์ใหม่")
    parts = cleaned.split(".")
    if len(parts) != 4 or parts[0].upper() != KEY_PREFIX:
        raise ValueError("รูปแบบคีย์ไม่ถูกต้อง (ต้องการ PFM2.<machine>.<exp>.<sig>)")
    mid, exp, sig = parts[1].upper(), parts[2], parts[3]
    if not re.fullmatch(r"[0-9A-F]{16}", mid):
        raise ValueError("รหัสเครื่องในคีย์ไม่ถูกต้อง")
    if not re.fullmatch(r"\d{8}", exp):
        raise ValueError("วันหมดอายุในคีย์ไม่ถูกต้อง")

    public_key = load_public_key()
    try:
        public_key.verify(_b64url_decode(sig), _payload(mid, exp))
    except (InvalidSignature, ValueError) as e:
        raise ValueError("คีย์ไม่ถูกต้องหรือไม่ได้ลงลายเซ็นด้วยกุญแจของผู้ขาย") from e

    if mid != machine_id.upper():
        raise ValueError("คีย์นี้ผูกกับเครื่องอื่น ไม่ใช้กับเครื่องนี้ได้")

    exp_end = datetime.strptime(exp, "%Y%m%d").replace(
        hour=23, minute=59, second=59, tzinfo=timezone.utc
    )
    now = now or datetime.now(timezone.utc)
    if now > exp_end:
        raise ValueError("ไลเซนต์หมดอายุแล้ว")

    days_left = max(0, (exp_end.date() - now.date()).days)
    return {
        "machine_id": mid,
        "expires": exp_end.date().isoformat(),
        "days_left": days_left,
        "key": f"{KEY_PREFIX}.{mid}.{exp}.{sig}",
    }


def license_path(data_dir: Path) -> Path:
    return Path(data_dir) / "license.json"


def clock_guard_path(data_dir: Path) -> Path:
    return Path(data_dir) / "clock_guard.json"


def _load_json(path: Path) -> Optional[dict[str, Any]]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError):
        return None


def _check_clock(data_dir: Path) -> None:
    """กันย้อนนาฬิกาแบบเบาๆ — ไม่กัน crack จริง แต่กัน casual"""
    now = int(time.time())
    path = clock_guard_path(data_dir)
    data = _load_json(path) or {}
    raw = data.get("max_seen_utc", 0)
    try:
        max_seen = int(raw or 0)
    except (TypeError, ValueError):
        # ไฟล์เพี้ยน — รีเซ็ตแทนการโชว์ traceback อังกฤษ
        max_seen = 0
        _atomic_write_json(path, {"max_seen_utc": now})
        return
    if max_seen and now + CLOCK_ROLLBACK_GRACE < max_seen:
        raise ValueError(
            "ตรวจพบนาฬิกาย้อนหลัง — ปรับเวลาเครื่องให้ถูกต้อง "
            "หรือขอคีย์ใหม่จากผู้ขายแล้วเปิดใช้อีกครั้ง"
        )
    if now - max_seen > CLOCK_WRITE_INTERVAL:
        _atomic_write_json(path, {"max_seen_utc": now})


def _reset_clock_guard(data_dir: Path) -> None:
    _atomic_write_json(clock_guard_path(data_dir), {"max_seen_utc": int(time.time())})


def _max_seen_utc(data_dir: Path) -> int:
    data = _load_json(clock_guard_path(data_dir)) or {}
    try:
        return int(data.get("max_seen_utc") or 0)
    except (TypeError, ValueError):
        return 0


def _effective_now(data_dir: Path) -> datetime:
    """เวลาสำหรับเช็ควันหมดอายุ = max(เวลาจริง, เวลาสูงสุดที่เคยเห็น)
    ย้อนนาฬิกาใน grace แล้วแอปยังใช้ได้ แต่ชุบชีวิตคีย์ที่หมดอายุแล้วไม่ได้"""
    now = datetime.now(timezone.utc)
    max_seen = _max_seen_utc(data_dir)
    if max_seen:
        seen = datetime.fromtimestamp(max_seen, tz=timezone.utc)
        if seen > now:
            return seen
    return now


def _make_status(
    *,
    licensed: bool,
    bypass: bool,
    machine_id: str,
    expires: Optional[str],
    days_left: Optional[int],
    message: str,
) -> dict[str, Any]:
    return {
        "licensed": licensed,
        "bypass": bypass,
        "machine_id": machine_id,
        "expires": expires,
        "days_left": days_left,
        "message": message,
        "demo_only": not licensed,
        "demo_doc": DEMO_DOC_NAME,
    }


def license_status(data_dir: Path) -> dict[str, Any]:
    data_dir = Path(data_dir)

    try:
        mid = get_machine_id(str(data_dir.resolve()))
    except RuntimeError as e:
        return _make_status(
            licensed=False,
            bypass=False,
            machine_id="—",
            expires=None,
            days_left=None,
            message=str(e),
        )

    if env_bool("LICENSE_BYPASS"):
        return _make_status(
            licensed=True,
            bypass=True,
            machine_id=mid,
            expires=None,
            days_left=None,
            message="โหมดพัฒนา (LICENSE_BYPASS)",
        )

    stored = _load_json(license_path(data_dir))
    if not stored or not stored.get("key"):
        return _make_status(
            licensed=False,
            bypass=False,
            machine_id=mid,
            expires=None,
            days_left=None,
            message=f"ยังไม่ได้เปิดใช้ไลเซนต์ — ทดลองสร้าง PDF ได้เฉพาะ {DEMO_DOC_NAME} ทางการ",
        )

    try:
        _check_clock(data_dir)
        info = parse_and_verify_key(stored["key"], mid, now=_effective_now(data_dir))
    except (ValueError, RuntimeError) as e:
        return _make_status(
            licensed=False,
            bypass=False,
            machine_id=mid,
            expires=None,
            days_left=None,
            message=str(e),
        )

    return _make_status(
        licensed=True,
        bypass=False,
        machine_id=mid,
        expires=info["expires"],
        days_left=info["days_left"],
        message=f"ไลเซนต์ใช้งานได้ถึง {info['expires']} (เหลือ ~{info['days_left']} วัน)",
    )


def can_fill_document(data_dir: Path, doc_name: str, pdf_path: Path) -> tuple[bool, str]:
    st = license_status(data_dir)
    if st["licensed"]:
        return True, ""
    name = Path(doc_name or "").name.lower()
    if name == DEMO_DOC_NAME:
        try:
            if is_canonical_demo_pdf(pdf_path):
                return True, ""
        except RuntimeError as e:
            return False, str(e)
        return (
            False,
            f"ไฟล์ {DEMO_DOC_NAME} ไม่ใช่แบบตัวอย่างทางการ (เนื้อหาถูกเปลี่ยน) — ต้องมีไลเซนต์",
        )
    return (
        False,
        "ต้องมีไลเซนต์ถึงจะสร้าง PDF ของเอกสารนี้ได้ "
        f"(รหัสเครื่อง: {st['machine_id']}) — ทดลองได้เฉพาะ {DEMO_DOC_NAME}",
    )


def save_license_file(data_dir: Path, key: str) -> None:
    """เก็บเฉพาะคีย์ — สถานะอื่น derive ตอนตรวจ"""
    _atomic_write_json(
        license_path(data_dir),
        {
            "key": key,
            "activated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    )


def activate_license(data_dir: Path, key: str) -> dict[str, Any]:
    data_dir = Path(data_dir)
    mid = get_machine_id(str(data_dir.resolve()))
    info = parse_and_verify_key(key, mid)
    stored = _load_json(license_path(data_dir)) or {}
    if info["key"] != stored.get("key"):
        # คีย์ใหม่จากผู้ขาย — เคลียร์สถานะนาฬิกาที่ค้าง
        _reset_clock_guard(data_dir)
    else:
        # คีย์เดิม — ต้องผ่านด่านนาฬิกาก่อน จึงจะถือว่าเปิดใช้สำเร็จ
        _check_clock(data_dir)
    save_license_file(data_dir, info["key"])
    st = license_status(data_dir)
    if not st["licensed"]:
        raise ValueError(st["message"] or "เปิดใช้ไลเซนต์ไม่สำเร็จ")
    return st
