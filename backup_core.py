"""สำรอง / กู้คืนข้อมูลงาน (CP3) — ไม่รวม license / machine_id"""
from __future__ import annotations

import io
import json
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO, Literal, Optional

from library_core import config_path, get_library_root, index_path, settings_path

BACKUP_FORMAT = 1
# ไฟล์/ชื่อที่ห้ามนำเข้าจาก ZIP แม้มีในไฟล์เก่า
FORBIDDEN_NAMES = frozenset({
    "machine_id",
    "license.json",
    "secret_key",
    "clock_guard.json",
})
RestoreMode = Literal["merge", "replace"]


def _now_stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d-%H%M%S")


def build_meta(
    *,
    app_version: str,
    username: str,
    data_dir: Path,
    library_root: Optional[Path],
) -> dict[str, Any]:
    return {
        "format": BACKUP_FORMAT,
        "kind": "pdf-form-marker-backup",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "app_version": app_version,
        "user": username,
        "data_dir": str(data_dir),
        "library_root": str(library_root) if library_root else None,
        "excludes": sorted(FORBIDDEN_NAMES) + ["logs/", "*.log"],
        "note_th": "ไฟล์นี้ไม่มี machine_id/license — เครื่องใหม่ต้องขอคีย์ไลเซนต์ใหม่",
    }


def _add_tree(zf: zipfile.ZipFile, src_dir: Path, arc_prefix: str) -> int:
    """ใส่ไฟล์ใต้ src_dir ลง ZIP — คืนจำนวนไฟล์"""
    if not src_dir.is_dir():
        return 0
    n = 0
    for dirpath, _dirnames, filenames in os.walk(src_dir):
        for name in filenames:
            if name in FORBIDDEN_NAMES:
                continue
            full = Path(dirpath) / name
            try:
                rel = full.relative_to(src_dir).as_posix()
            except ValueError:
                continue
            zf.write(full, arcname=f"{arc_prefix}/{rel}")
            n += 1
    return n


def create_backup_zip(
    *,
    data_dir: Path,
    username: str,
    user_root: Path,
    app_version: str,
) -> tuple[io.BytesIO, str, dict[str, Any]]:
    """สร้าง ZIP ใน memory — คืน (buf, filename, meta)"""
    data_dir = Path(data_dir)
    user_root = Path(user_root)
    lib_root = get_library_root(data_dir)
    meta = build_meta(
        app_version=app_version,
        username=username,
        data_dir=data_dir,
        library_root=lib_root,
    )
    counts = {"uploads": 0, "templates": 0, "output": 0, "library": 0}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        counts["uploads"] = _add_tree(zf, user_root / "uploads", "user/uploads")
        counts["templates"] = _add_tree(
            zf, user_root / "templates_json", "user/templates_json"
        )
        counts["output"] = _add_tree(zf, user_root / "output", "user/output")
        seeded = user_root / "seeded.json"
        if seeded.is_file():
            zf.write(seeded, arcname="user/seeded.json")

        lib_cfg = config_path(data_dir)
        if lib_cfg.is_file():
            zf.write(lib_cfg, arcname="library/library.json")
            counts["library"] += 1
        if lib_root is not None:
            for label, p in (
                ("library/pdfmarker/settings.json", settings_path(lib_root)),
                ("library/pdfmarker/index.json", index_path(lib_root)),
            ):
                if p.is_file():
                    zf.write(p, arcname=label)
                    counts["library"] += 1

        meta["counts"] = counts
        zf.writestr("meta.json", json.dumps(meta, ensure_ascii=False, indent=2) + "\n")

    buf.seek(0)
    filename = f"pdfmarker-backup-{_now_stamp()}.zip"
    return buf, filename, meta


def read_backup_meta(fileobj: BinaryIO) -> dict[str, Any]:
    with zipfile.ZipFile(fileobj, "r") as zf:
        if "meta.json" not in zf.namelist():
            raise ValueError("ไม่ใช่ไฟล์สำรองของ PDF Form Marker (ไม่มี meta.json)")
        meta = json.loads(zf.read("meta.json").decode("utf-8"))
        if meta.get("kind") != "pdf-form-marker-backup":
            raise ValueError("ชนิดไฟล์สำรองไม่ถูกต้อง")
        return meta


def restore_backup(
    fileobj: BinaryIO,
    *,
    user_root: Path,
    data_dir: Path,
    mode: RestoreMode = "merge",
) -> dict[str, Any]:
    """กู้ ZIP ลง user_root + library.json — ไม่แตะ machine_id/license

    mode=merge: ไม่ทับไฟล์ที่มีอยู่แล้ว
    mode=replace: ล้าง uploads/templates_json/output ของ user แล้วแตกทับ

    แตก library.json ก่อนเสมอ แล้วค่อย .pdfmarker/* — กันลำดับใน ZIP ทำให้ข้ามดัชนีคลัง
    """
    user_root = Path(user_root)
    data_dir = Path(data_dir)
    fileobj.seek(0)
    meta = read_backup_meta(fileobj)
    fileobj.seek(0)

    uploads = user_root / "uploads"
    templates = user_root / "templates_json"
    output = user_root / "output"
    for d in (uploads, templates, output):
        d.mkdir(parents=True, exist_ok=True)

    if mode == "replace":
        for d in (uploads, templates, output):
            for p in d.rglob("*"):
                if p.is_file():
                    p.unlink()
        seeded = user_root / "seeded.json"
        if seeded.is_file():
            seeded.unlink()

    written = 0
    skipped = 0

    def _write_bytes(dest: Path, data: bytes) -> bool:
        nonlocal written, skipped
        if mode == "merge" and dest.exists():
            skipped += 1
            return False
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        written += 1
        return True

    with zipfile.ZipFile(fileobj, "r") as zf:
        members = [
            info
            for info in zf.infolist()
            if not info.is_dir() and not info.filename.replace("\\", "/").endswith("/")
        ]

        # —— รอบ 1: library/library.json เท่านั้น ——
        for info in members:
            name = info.filename.replace("\\", "/")
            if name != "library/library.json":
                continue
            _write_bytes(config_path(data_dir), zf.read(info))

        # —— รอบ 2: user/* และ library/pdfmarker/* ——
        for info in members:
            name = info.filename.replace("\\", "/")
            if name in ("meta.json", "library/library.json"):
                continue
            base = Path(name).name
            if base in FORBIDDEN_NAMES:
                skipped += 1
                continue

            if name.startswith("user/"):
                rel = name[len("user/") :]
                if not rel or ".." in Path(rel).parts:
                    skipped += 1
                    continue
                dest = (user_root / rel).resolve()
                try:
                    dest.relative_to(user_root.resolve())
                except ValueError:
                    skipped += 1
                    continue
                _write_bytes(dest, zf.read(info))

            elif name.startswith("library/"):
                rel = name[len("library/") :]
                # รับเฉพาะ pdfmarker ใต้คลัง — ไม่รับ *library.json ปลอมใน path อื่น
                if not rel.startswith("pdfmarker/"):
                    skipped += 1
                    continue
                lib_root = get_library_root(data_dir)
                if lib_root is None:
                    skipped += 1
                    continue
                sub = rel[len("pdfmarker/") :]
                if not sub or ".." in Path(sub).parts:
                    skipped += 1
                    continue
                marker_root = (lib_root / ".pdfmarker").resolve()
                dest = (marker_root / sub).resolve()
                try:
                    dest.relative_to(marker_root)
                except ValueError:
                    skipped += 1
                    continue
                _write_bytes(dest, zf.read(info))
            else:
                skipped += 1

    return {
        "ok": True,
        "mode": mode,
        "written": written,
        "skipped": skipped,
        "meta": {
            "created_at": meta.get("created_at"),
            "app_version": meta.get("app_version"),
            "user": meta.get("user"),
            "library_root": meta.get("library_root"),
        },
        "note_th": "ไม่ได้กู้ machine_id/license — ถ้าเครื่องใหม่ต้องเปิดใช้คีย์ใหม่",
    }


def export_template_bytes(path: Path, name: str) -> tuple[bytes, str]:
    data = path.read_bytes()
    safe = "".join(c if c.isalnum() or c in "-_ก-๙" else "_" for c in name) or "template"
    return data, f"{safe}.tpl.json"


def list_formpack_templates(pack_dir: Path) -> list[dict[str, str]]:
    if not pack_dir.is_dir():
        return []
    out = []
    for p in sorted(pack_dir.glob("*.json")):
        out.append({"name": p.stem, "file": p.name})
    return out


def install_formpack(
    pack_dir: Path,
    templates_dir: Path,
    *,
    overwrite: bool = False,
) -> dict[str, Any]:
    templates_dir.mkdir(parents=True, exist_ok=True)
    installed: list[str] = []
    skipped: list[str] = []
    if not pack_dir.is_dir():
        raise ValueError("ไม่พบแพ็กฟอร์ม")
    for src in sorted(pack_dir.glob("*.json")):
        dest = templates_dir / src.name
        if dest.exists() and not overwrite:
            skipped.append(src.stem)
            continue
        dest.write_bytes(src.read_bytes())
        installed.append(src.stem)
    return {"installed": installed, "skipped": skipped}
