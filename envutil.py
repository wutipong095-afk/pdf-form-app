"""ยูทิลร่วมทั้งแอปและสคริปต์ผู้ขาย"""
from __future__ import annotations

import os
from pathlib import Path

BASE = Path(__file__).resolve().parent


def load_dotenv(env_path: Path | None = None) -> None:
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
