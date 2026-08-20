"""สะพานระหว่างไฟล์ .formdd กับใบงาน — นำเข้า ส่งออก และย้ายข้อมูลเก่า"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import form_store
import job_core
import sheet_core
from fields_core import FormDataError

log = logging.getLogger(__name__)

MIGRATED_MARKER = ".migrated-from-formdd"
LEGACY_MIGRATED_MARKER = ".migrated-from-fromdd"  # หมายของรุ่นก่อนเปลี่ยนชื่อ


def import_formdd(
    sheets_dir: Path,
    forms_dir: Path,
    src: Path,
    *,
    base_name: str = "",
) -> dict[str, Any]:
    """แตก .formdd เป็นใบงาน + สแนปช็อตฟอร์ม — คืน payload ของใบที่สร้าง"""
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
    # ฐานของชื่อต้องเป็นชื่อฟอร์ม ไม่ใช่ชื่อใบที่คิดแล้ว ไม่งั้นแก้ค่าแรกแล้วจะได้
    # «ใบลา — โรงเรียนเก่า — โรงเรียนใหม่» ไฟล์เก่าที่ไม่มี title_base ใช้ template_name แทน
    title_base = str(meta.get("title_base") or meta.get("template_name") or title)
    title_auto = bool(meta.get("title_auto", True))
    name = sheet_core.unique_sheet_name(sheets_dir, base_name or title)
    path = Path(sheets_dir) / name
    try:
        payload = sheet_core.save_sheet(path, {
            "title": title,
            "rename": not title_auto,
            "title_base": title_base,
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


def export_formdd(dest: Path, forms_dir: Path, sheet: dict[str, Any]) -> Path:
    """แพ็กใบงาน + สแนปช็อตกลับเป็น .formdd ไฟล์เดียวจบในตัว"""
    dest = Path(dest)
    pdf = form_store.require_pdf(forms_dir, str(sheet.get("form_sha") or ""))
    job_core.write_job(
        dest,
        pdf.read_bytes(),
        job_core.build_payload(
            title=str(sheet.get("title") or dest.stem),
            title_base=str(sheet.get("title_base") or ""),
            title_auto=bool(sheet.get("title_auto", True)),
            source_doc=str(sheet.get("source_doc") or ""),
            template_name=str(sheet.get("template_name") or ""),
            fields=sheet.get("fields") or [],
        ),
    )
    return dest


def migrate_jobs_dir(jobs_dir: Path, sheets_dir: Path, forms_dir: Path) -> dict[str, int]:
    """ย้าย .formdd ที่ค้างอยู่ไปเป็นใบงาน — ทำครั้งเดียวต่อผู้ใช้ ไม่ลบไฟล์เดิม

    ไฟล์เดิมเก็บไว้เฉย ๆ เผื่อผู้ใช้อยากได้กลับ — เป็นฟอร์แมตส่งออกอยู่แล้ว
    """
    jobs_dir, sheets_dir, forms_dir = Path(jobs_dir), Path(sheets_dir), Path(forms_dir)
    done = {"moved": 0, "failed": 0}
    if not jobs_dir.is_dir():
        return done
    stale = sorted(jobs_dir.glob("*" + job_core.JOB_EXT)) + sorted(
        jobs_dir.glob("*" + job_core.LEGACY_JOB_EXT)
    )
    for src in stale:
        try:
            if src.stat().st_size == 0:
                continue
            import_formdd(sheets_dir, forms_dir, src, base_name=src.stem)
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
    แล้วจะย้าย .formdd เดิมซ้ำอีกรอบจนได้ใบงานซ้ำ
    """
    root = Path(jobs_dir).parent
    marker = root / MIGRATED_MARKER
    if marker.exists() or (root / LEGACY_MIGRATED_MARKER).exists():
        return
    Path(sheets_dir).mkdir(parents=True, exist_ok=True)
    done = migrate_jobs_dir(jobs_dir, sheets_dir, forms_dir)
    if done["moved"] or done["failed"]:
        log.info("migrated formdd jobs moved=%s failed=%s", done["moved"], done["failed"])
    try:
        marker.write_text("", encoding="utf-8")
    except OSError:
        pass
