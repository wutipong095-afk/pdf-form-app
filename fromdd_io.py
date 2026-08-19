"""สะพานระหว่างไฟล์ .fromdd กับใบงาน — นำเข้า ส่งออก และย้ายข้อมูลเก่า"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import form_store
import job_core
import sheet_core
from fields_core import FormDataError

log = logging.getLogger(__name__)

MIGRATED_MARKER = ".migrated-from-fromdd"


def import_fromdd(
    sheets_dir: Path,
    forms_dir: Path,
    src: Path,
    *,
    base_name: str = "",
) -> dict[str, Any]:
    """แตก .fromdd เป็นใบงาน + สแนปช็อตฟอร์ม — คืน payload ของใบที่สร้าง"""
    src = Path(src)
    meta = job_core.read_job(src)
    pdf_bytes = job_core.read_job_pdf_bytes(src)
    sha = form_store.store_pdf(
        forms_dir,
        pdf_bytes,
        source_doc=str(meta.get("source_doc") or ""),
        display_name=str(meta.get("template_name") or meta.get("title") or src.stem),
    )
    title = str(meta.get("title") or src.stem)
    name = sheet_core.unique_sheet_name(sheets_dir, base_name or title)
    path = Path(sheets_dir) / name
    try:
        payload = sheet_core.save_sheet(path, {
            "title_base": title,
            "form_sha": sha,
            "source_doc": meta.get("source_doc") or "",
            "template_name": meta.get("template_name") or "",
            "fields": meta.get("fields") or [],
        })
    except Exception:
        try:
            if path.is_file() and path.stat().st_size == 0:
                path.unlink()
        except OSError:
            pass
        raise
    payload["name"] = name
    return payload


def export_fromdd(dest: Path, forms_dir: Path, sheet: dict[str, Any]) -> Path:
    """แพ็กใบงาน + สแนปช็อตกลับเป็น .fromdd ไฟล์เดียวจบในตัว"""
    dest = Path(dest)
    pdf = form_store.require_pdf(forms_dir, str(sheet.get("form_sha") or ""))
    job_core.write_job(
        dest,
        pdf.read_bytes(),
        job_core.build_payload(
            title=str(sheet.get("title") or dest.stem),
            source_doc=str(sheet.get("source_doc") or ""),
            template_name=str(sheet.get("template_name") or ""),
            fields=sheet.get("fields") or [],
        ),
    )
    return dest


def migrate_jobs_dir(jobs_dir: Path, sheets_dir: Path, forms_dir: Path) -> dict[str, int]:
    """ย้าย .fromdd ที่ค้างอยู่ไปเป็นใบงาน — ทำครั้งเดียวต่อผู้ใช้ ไม่ลบไฟล์เดิม

    ไฟล์เดิมเก็บไว้เฉย ๆ เผื่อผู้ใช้อยากได้กลับ — เป็นฟอร์แมตส่งออกอยู่แล้ว
    """
    jobs_dir, sheets_dir, forms_dir = Path(jobs_dir), Path(sheets_dir), Path(forms_dir)
    done = {"moved": 0, "failed": 0}
    if not jobs_dir.is_dir():
        return done
    for src in sorted(jobs_dir.glob("*" + job_core.JOB_EXT)):
        try:
            if src.stat().st_size == 0:
                continue
            import_fromdd(sheets_dir, forms_dir, src, base_name=src.stem)
            done["moved"] += 1
        except (FormDataError, OSError) as e:
            done["failed"] += 1
            log.warning("migrate job file failed name=%s err=%s", src.name, e)
    # แคชที่รูปแบบเดิมต้องใช้ — ไม่ต้องแล้วเพราะสแนปช็อตเก็บตาม hash
    cache = jobs_dir / ".cache"
    if cache.is_dir():
        for p in cache.glob("*.pdf"):
            try:
                p.unlink()
            except OSError:
                pass
        try:
            cache.rmdir()
        except OSError:
            pass
    return done


def ensure_migrated(jobs_dir: Path, sheets_dir: Path, forms_dir: Path) -> None:
    """ทำครั้งเดียวต่อผู้ใช้ — กันด้วยไฟล์หมายไว้ ไม่ใช่การสแกนซ้ำทุกรีเควสต์

    หมายไว้ที่รากของผู้ใช้ ไม่ใช่ใน sheets/ เพราะกู้คืนแบบแทนที่ล้าง sheets/ ทิ้ง
    แล้วจะย้าย .fromdd เดิมซ้ำอีกรอบจนได้ใบงานซ้ำ
    """
    marker = Path(jobs_dir).parent / MIGRATED_MARKER
    if marker.exists():
        return
    Path(sheets_dir).mkdir(parents=True, exist_ok=True)
    done = migrate_jobs_dir(jobs_dir, sheets_dir, forms_dir)
    if done["moved"] or done["failed"]:
        log.info("migrated fromdd jobs moved=%s failed=%s", done["moved"], done["failed"])
    try:
        marker.write_text("", encoding="utf-8")
    except OSError:
        pass
