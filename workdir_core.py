"""โฟลเดอร์เก็บงานของผู้ใช้ — เลือกเองได้ว่าจะให้ใบงานไปอยู่ที่ไหน

ค่าเริ่มต้นคือใต้โฟลเดอร์ข้อมูลของโปรแกรม ซึ่งผู้ใช้มองไม่เห็นจาก Explorer
ตั้งค่าใหม่ได้ เช่น Documents\\FromDD หรือไดรฟ์ส่วนกลางของโรงเรียน

เก็บค่าไว้ที่ <user_root>/workdir.json — แยกต่อผู้ใช้ ไม่ปนกัน
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import time
from pathlib import Path
from typing import Any, Iterable, Optional

log = logging.getLogger(__name__)

CONFIG_NAME = "workdir.json"
# โฟลเดอร์ที่ย้ายตามไปด้วยเมื่อเปลี่ยนที่เก็บงาน
WORK_SUBDIRS = ("sheets", "forms", "output")


class WorkDirError(ValueError):
    """เลือกโฟลเดอร์เก็บงานไม่ได้"""


def config_path(user_root: Path) -> Path:
    return Path(user_root) / CONFIG_NAME


def _read_config(user_root: Path) -> dict[str, Any]:
    try:
        data = json.loads(config_path(user_root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_config(user_root: Path, path: Optional[Path]) -> None:
    dest = config_path(user_root)
    dest.parent.mkdir(parents=True, exist_ok=True)
    body = {} if path is None else {"path": str(path)}
    raw = json.dumps(body, ensure_ascii=False, indent=2) + "\n"
    tmp = dest.with_name(dest.name + ".tmp")
    try:
        tmp.write_text(raw, encoding="utf-8")
        os.replace(tmp, dest)
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def configured(user_root: Path) -> Optional[Path]:
    """ค่าที่ตั้งไว้ — ยังไม่ได้ตรวจว่าใช้ได้จริงไหม"""
    raw = str(_read_config(user_root).get("path") or "").strip()
    if not raw:
        return None
    try:
        return Path(raw).expanduser()
    except (OSError, ValueError):
        return None


def _usable(path: Path) -> bool:
    """สร้างได้และเขียนได้จริง — ไดรฟ์เครือข่ายที่หลุดต้องไม่ทำให้แอปพัง"""
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    probe = path / ".fromdd-write-test"
    try:
        probe.write_text("", encoding="utf-8")
        probe.unlink()
    except OSError:
        return False
    return True


# user_paths() ถูกเรียกแทบทุกรีเควสต์ — อย่าไปแหย่ไดรฟ์เครือข่ายทุกครั้ง
_RESOLVED: dict[str, tuple[float, Path]] = {}
CHECK_EVERY_S = 20.0


def forget(user_root: Path) -> None:
    _RESOLVED.pop(str(Path(user_root)), None)


def resolve(user_root: Path) -> Path:
    """โฟลเดอร์เก็บงานที่ใช้ได้จริงตอนนี้ — ถอยกลับค่าเริ่มต้นถ้าที่ตั้งไว้ใช้ไม่ได้"""
    user_root = Path(user_root)
    key = str(user_root)
    hit = _RESOLVED.get(key)
    now = time.monotonic()
    if hit and now - hit[0] < CHECK_EVERY_S:
        return hit[1]

    chosen = configured(user_root)
    if chosen is None:
        found = user_root
    elif _usable(chosen):
        found = chosen
    else:
        log.warning("work dir unavailable, falling back to default path=%s", chosen)
        found = user_root
    if len(_RESOLVED) > 64:
        _RESOLVED.clear()
    _RESOLVED[key] = (now, found)
    return found


def status(user_root: Path) -> dict[str, Any]:
    user_root = Path(user_root)
    chosen = configured(user_root)
    active = resolve(user_root)
    return {
        "path": str(active),
        "default_path": str(user_root),
        "custom": chosen is not None,
        # ตั้งไว้แต่เข้าไม่ได้ตอนนี้ — เช่นไดรฟ์เครือข่ายหลุด
        "unavailable": chosen is not None and Path(active) == user_root,
        "configured_path": str(chosen) if chosen else "",
    }


def _validate(new_dir: Path, user_root: Path, forbidden: Iterable[Path]) -> Path:
    try:
        new_dir = new_dir.expanduser().resolve()
    except (OSError, ValueError) as e:
        raise WorkDirError("invalid work folder") from e
    if new_dir.exists() and not new_dir.is_dir():
        raise WorkDirError("work folder must be a directory")
    for bad in forbidden:
        try:
            bad = Path(bad).resolve()
        except (OSError, ValueError):
            continue
        if new_dir == bad or bad in new_dir.parents:
            raise WorkDirError("work folder must not be inside the program folder")
    if not _usable(new_dir):
        raise WorkDirError("cannot write to that folder")
    return new_dir


def _move_tree(src: Path, dest: Path) -> int:
    """ย้ายไฟล์ทั้งหมดจาก src ไป dest — ไม่ทับของที่มีอยู่แล้ว คืนจำนวนที่ย้าย"""
    if not src.is_dir():
        return 0
    dest.mkdir(parents=True, exist_ok=True)
    moved = 0
    for item in sorted(src.iterdir()):
        if not item.is_file():
            continue
        target = dest / item.name
        if target.exists():
            continue
        try:
            shutil.move(str(item), str(target))
            moved += 1
        except OSError:
            log.exception("move work file failed name=%s", item.name)
    return moved


def set_work_dir(
    user_root: Path,
    raw_path: str,
    *,
    forbidden: Iterable[Path] = (),
    move: bool = True,
) -> dict[str, Any]:
    """ตั้งโฟลเดอร์เก็บงานใหม่ แล้วย้ายงานที่มีอยู่ตามไปด้วย"""
    user_root = Path(user_root)
    if not str(raw_path or "").strip():
        raise WorkDirError("choose a folder first")
    new_dir = _validate(Path(str(raw_path).strip()), user_root, forbidden)
    forget(user_root)
    old_dir = resolve(user_root)

    moved = 0
    if move and new_dir != old_dir:
        for name in WORK_SUBDIRS:
            moved += _move_tree(old_dir / name, new_dir / name)
    for name in WORK_SUBDIRS:
        (new_dir / name).mkdir(parents=True, exist_ok=True)

    _write_config(user_root, None if new_dir == user_root else new_dir)
    forget(user_root)
    log.info("work dir set path=%s moved=%s", new_dir, moved)
    out = status(user_root)
    out["moved"] = moved
    return out


def reset(user_root: Path, *, move: bool = True) -> dict[str, Any]:
    """กลับไปใช้ที่เก็บเริ่มต้นใต้โฟลเดอร์ข้อมูลของโปรแกรม"""
    return set_work_dir(user_root, str(Path(user_root)), forbidden=(), move=move)
