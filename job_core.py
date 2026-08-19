"""ไฟล์ .fromdd — ZIP ของ PDF ต้นฉบับเปล่า + ค่าที่กรอก

ตั้งแต่มีคลังสแนปช็อต (form_store) + ใบงาน (sheet_core) ฟอร์แมตนี้ไม่ใช่ที่เก็บ
งานประจำวันอีกแล้ว แต่เป็นฟอร์แมต **ส่งออก/นำเข้า** สำหรับส่งใบงานให้เครื่องอื่น
ที่ไม่มีฟอร์มต้นฉบับ — และเป็นตัวอ่านไฟล์เก่าตอนย้ายข้อมูล
"""
from __future__ import annotations

import json
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fields_core import FormDataError, normalize_fields
from history_core import safe_stem

JOB_EXT = ".fromdd"
FORM_PDF = "form.pdf"
JOB_JSON = "job.json"
JOB_KIND = "fromdd-job"
JOB_VERSION = 1
MAX_PDF_BYTES = 64 * 1024 * 1024
MAX_JSON_BYTES = 1024 * 1024

JobError = FormDataError


def job_filename(name: str) -> str:
    body = str(name or "").replace("\\", "/").split("/")[-1]
    if not body:
        raise JobError("invalid job file name")
    stem = body[: -len(JOB_EXT)] if body.lower().endswith(JOB_EXT) else body
    return safe_stem(stem) + JOB_EXT


def _zip_names(zf: zipfile.ZipFile) -> set[str]:
    return {n.replace("\\", "/").lstrip("/") for n in zf.namelist() if n and not n.endswith("/")}


def build_payload(
    *,
    title: str,
    source_doc: str,
    template_name: str,
    fields: Any,
) -> dict[str, Any]:
    return {
        "version": JOB_VERSION,
        "kind": JOB_KIND,
        "title": (title or "").strip()[:120] or "job",
        "source_doc": (source_doc or "").strip(),
        "template_name": (template_name or "").strip()[:120],
        "fields": normalize_fields(fields),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def _read_payload_bytes(raw: bytes) -> dict[str, Any]:
    if len(raw) > MAX_JSON_BYTES:
        raise JobError("job.json too large")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise JobError("job.json is not valid JSON") from e
    if not isinstance(data, dict) or data.get("kind") != JOB_KIND:
        raise JobError("not a FromDD job file")
    data["fields"] = normalize_fields(data.get("fields") or [])
    data["title"] = str(data.get("title") or "").strip()[:120] or "job"
    data["source_doc"] = str(data.get("source_doc") or "").strip()
    data["template_name"] = str(data.get("template_name") or "").strip()[:120]
    return data


def read_job(path: Path) -> dict[str, Any]:
    path = Path(path)
    try:
        with zipfile.ZipFile(path, "r") as zf:
            names = _zip_names(zf)
            if FORM_PDF not in names or JOB_JSON not in names:
                raise JobError("job file is incomplete")
            extra = names - {FORM_PDF, JOB_JSON}
            if extra:
                raise JobError("job file has unexpected members")
            if zf.getinfo(FORM_PDF).file_size > MAX_PDF_BYTES:
                raise JobError("packed PDF is too large")
            if zf.getinfo(JOB_JSON).file_size > MAX_JSON_BYTES:
                raise JobError("job.json too large")
            return _read_payload_bytes(zf.read(JOB_JSON))
    except JobError:
        raise
    except (OSError, KeyError, zipfile.BadZipFile) as e:
        raise JobError("could not read job file") from e


def read_job_pdf_bytes(path: Path) -> bytes:
    path = Path(path)
    try:
        with zipfile.ZipFile(path, "r") as zf:
            names = _zip_names(zf)
            if FORM_PDF not in names:
                raise JobError("job file is incomplete")
            if zf.getinfo(FORM_PDF).file_size > MAX_PDF_BYTES:
                raise JobError("packed PDF is too large")
            data = zf.read(FORM_PDF)
    except JobError:
        raise
    except (OSError, KeyError, zipfile.BadZipFile) as e:
        raise JobError("could not read job file") from e
    if not data.startswith(b"%PDF-"):
        raise JobError("packed file is not a PDF")
    return data


def write_job(path: Path, pdf_bytes: bytes, payload: dict[str, Any]) -> None:
    if not pdf_bytes.startswith(b"%PDF-"):
        raise JobError("source is not a PDF")
    if len(pdf_bytes) > MAX_PDF_BYTES:
        raise JobError("PDF is too large")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = dict(payload)
    body["fields"] = normalize_fields(body.get("fields") or [])
    body["version"] = JOB_VERSION
    body["kind"] = JOB_KIND
    raw_json = json.dumps(body, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    tmp = path.with_name(path.name + ".tmp")
    try:
        with zipfile.ZipFile(tmp, "w") as zf:
            # PDF บีบอัดมาแล้ว — deflate ซ้ำแทบไม่ลดขนาดแต่กิน CPU
            zf.writestr(FORM_PDF, pdf_bytes, compress_type=zipfile.ZIP_STORED)
            zf.writestr(JOB_JSON, raw_json.encode("utf-8"), compress_type=zipfile.ZIP_DEFLATED)
        os.replace(tmp, path)
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise
