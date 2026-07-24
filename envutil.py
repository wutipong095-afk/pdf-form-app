"""ยูทิลร่วมทั้งแอปและสคริปต์ผู้ขาย"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _resolve_base() -> Path:
    """รากไฟล์แอป (fonts/demo/templates) — รองรับ PyInstaller onedir"""
    if getattr(sys, "frozen", False):
        mei = getattr(sys, "_MEIPASS", None)
        if mei:
            return Path(mei)
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


BASE = _resolve_base()
APP_NAME = "PDFFormMarker"
APP_VERSION = "0.1.0"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def load_dotenv(env_path: Path | None = None) -> None:
    # ตัวติดตั้งลูกค้าไม่โหลด .env (กัน LICENSE_BYPASS / ค่าผิดพลาด)
    if is_frozen() and env_path is None:
        return
    path = env_path or (BASE / ".env")
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def app_root_dir() -> Path:
    """รากข้อมูลระบบ: %LOCALAPPDATA%\\PDFFormMarker บน Windows, ไม่เช่นนั้น BASE/.pdfmarker"""
    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA", "").strip()
        if local:
            return Path(local) / APP_NAME
    return BASE / ".pdfmarker"


def default_data_dir() -> Path:
    return app_root_dir() / "data"


def default_log_dir() -> Path:
    return app_root_dir() / "logs"


def legacy_project_data_dir() -> Path:
    return (BASE / "data").resolve()


def _legacy_data_in_use(path: Path) -> bool:
    """โฟลเดอร์ data ในโปรเจกต์มี marker จริง — ไม่ใช้ความไม่ว่างของโฟลเดอร์

    ไฟล์หลง (.gitkeep ฯลฯ) ต้องไม่สลับ DATA_DIR / machine_id
    """
    if not path.is_dir():
        return False
    if (path / "machine_id").is_file() or (path / "license.json").is_file():
        return True
    users = path / "users"
    if not users.is_dir():
        return False
    try:
        for child in users.iterdir():
            if child.is_dir():
                try:
                    next(child.iterdir())
                    return True
                except StopIteration:
                    continue
            elif child.is_file():
                return True
    except OSError:
        return False
    return False


def resolve_data_dir() -> Path:
    """ลำดับ: DATA_DIR จาก env → ./data เดิมถ้าเคยใช้ → AppData / .pdfmarker

    โหมดติดตั้ง (frozen) ใช้ AppData เสมอ — ไม่ใช้ data ใต้โฟลเดอร์ติดตั้ง
    """
    raw = os.environ.get("DATA_DIR", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    if is_frozen():
        return default_data_dir().resolve()
    legacy = legacy_project_data_dir()
    if _legacy_data_in_use(legacy):
        return legacy
    return default_data_dir().resolve()


def resolve_log_dir(data_dir: Path | None = None) -> Path:
    raw = os.environ.get("LOG_DIR", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    if data_dir is not None:
        explicit = bool(os.environ.get("DATA_DIR", "").strip())
        legacy = data_dir.resolve() == legacy_project_data_dir()
        # Docker / DATA_DIR ตั้งเอง / data ในโปรเจกต์ — เก็บ log คู่กับข้อมูล
        if explicit or legacy:
            return (data_dir / "logs").resolve()
    return default_log_dir().resolve()
