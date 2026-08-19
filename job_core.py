"""ไฟล์งาน .fromdd — ZIP ของ PDF ต้นฉบับว่าง + ค่าที่กรอก เปิดแก้ต่อได้

เก็บใต้ data/users/<user>/jobs/ ไม่ใช่โฟลเดอร์ติดตั้ง
เอกสารในแอปอ้างด้วย @job.{filename}
"""
from __future__ import annotations

import json
import math
import os
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from history_core import HISTORY_LIMIT, form_group, safe_stem

JOB_EXT = ".fromdd"
JOB_DOC_PREFIX = "@job."
FORM_PDF = "form.pdf"
JOB_JSON = "job.json"
JOB_KIND = "fromdd-job"
JOB_VERSION = 1
CACHE_DIR_NAME = ".cache"
MAX_FIELDS = 500
MAX_VALUE_LEN = 2000
MAX_PAGE = 9999
MAX_COORD = 1_000_000.0
MIN_SIZE = 0.1
MAX_SIZE = 1_000.0
MAX_PDF_BYTES = 64 * 1024 * 1024
MAX_JSON_BYTES = 1024 * 1024


class JobError(ValueError):
    """ไฟล์งานเสียหรือคำขอไม่ถูกต้อง"""


def is_job_doc(doc: str | None) -> bool:
    return str(doc or "").startswith(JOB_DOC_PREFIX)


def make_job_doc(filename: str) -> str:
    return JOB_DOC_PREFIX + Path(filename).name


def job_filename_from_doc(doc: str) -> str:
    body = str(doc or "")
    if body.startswith(JOB_DOC_PREFIX):
        body = body[len(JOB_DOC_PREFIX) :]
    body = body.replace("\\", "/").split("/")[-1]
    if not body:
        raise JobError("invalid job document id")
    stem = body[: -len(JOB_EXT)] if body.lower().endswith(JOB_EXT) else body
    return safe_stem(stem) + JOB_EXT


def _zip_names(zf: zipfile.ZipFile) -> set[str]:
    return {n.replace("\\", "/").lstrip("/") for n in zf.namelist() if n and not n.endswith("/")}


def unique_job_name(jobs_dir: Path, base: str, *, now: Optional[float] = None) -> str:
    """จองชื่อ .fromdd แบบ exclusive — ไม่ทับงานวินาทีเดียวกัน"""
    jobs_dir = Path(jobs_dir)
    jobs_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(now if now is not None else time.time()))
    stem = f"{safe_stem(base) or 'job'}-{stamp}"
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    for n in range(0, 1000):
        name = f"{stem}{JOB_EXT}" if n == 0 else f"{stem}-{n}{JOB_EXT}"
        path = jobs_dir / name
        try:
            fd = os.open(path, flags)
        except FileExistsError:
            continue
        os.close(fd)
        return name
    raise OSError("could not allocate unique job name")


def _field_int(val: Any, default: int, *, lo: int, hi: int) -> int:
    if val is None or val == "":
        val = default
    try:
        n = int(val)
    except (TypeError, ValueError, OverflowError) as e:
        raise JobError("invalid field geometry") from e
    if not lo <= n <= hi:
        raise JobError("invalid field geometry")
    return n


def _field_float(val: Any, default: float, *, lo: float, hi: float) -> float:
    if val is None or val == "":
        val = default
    try:
        n = float(val)
    except (TypeError, ValueError, OverflowError) as e:
        raise JobError("invalid field geometry") from e
    # nan/inf เขียนเป็น JSON มาตรฐานไม่ได้ และทำให้ fill พังตอนวางข้อความ
    if not math.isfinite(n) or not lo <= n <= hi:
        raise JobError("invalid field geometry")
    return n


def normalize_fields(fields: Any) -> list[dict[str, Any]]:
    if not isinstance(fields, list):
        raise JobError("fields must be a list")
    if len(fields) > MAX_FIELDS:
        raise JobError("too many fields")
    out: list[dict[str, Any]] = []
    for item in fields:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        out.append({
            "name": name[:80],
            "page": _field_int(item.get("page"), 0, lo=0, hi=MAX_PAGE),
            "x": _field_float(item.get("x"), 0, lo=-MAX_COORD, hi=MAX_COORD),
            "y": _field_float(item.get("y"), 0, lo=-MAX_COORD, hi=MAX_COORD),
            "size": _field_float(item.get("size"), 14, lo=MIN_SIZE, hi=MAX_SIZE),
            "value": str(item.get("value") or "")[:MAX_VALUE_LEN],
        })
    return out


def layout_fields(fields: Any) -> list[dict[str, Any]]:
    """เทมเพลตเก็บโครงอย่างเดียว — ไม่เก็บค่าของใบนั้น"""
    out = []
    for f in normalize_fields(fields):
        f["value"] = ""
        out.append(f)
    return out


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
            info = zf.getinfo(FORM_PDF)
            if info.file_size > MAX_PDF_BYTES:
                raise JobError("packed PDF is too large")
            meta = zf.getinfo(JOB_JSON)
            if meta.file_size > MAX_JSON_BYTES:
                raise JobError("job.json too large")
            return _read_payload_bytes(zf.read(JOB_JSON))
    except JobError:
        raise
    except (OSError, zipfile.BadZipFile) as e:
        raise JobError("could not read job file") from e


def read_job_pdf_bytes(path: Path) -> bytes:
    path = Path(path)
    try:
        with zipfile.ZipFile(path, "r") as zf:
            names = _zip_names(zf)
            if FORM_PDF not in names:
                raise JobError("job file is incomplete")
            info = zf.getinfo(FORM_PDF)
            if info.file_size > MAX_PDF_BYTES:
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
    raw_json = json.dumps(body, ensure_ascii=False, indent=2) + "\n"
    tmp = path.with_name(path.name + ".tmp")
    try:
        with zipfile.ZipFile(tmp, "w") as zf:
            zf.writestr(FORM_PDF, pdf_bytes, compress_type=zipfile.ZIP_STORED)
            zf.writestr(JOB_JSON, raw_json.encode("utf-8"), compress_type=zipfile.ZIP_DEFLATED)
        os.replace(tmp, path)
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def save_job(path: Path, payload: dict[str, Any], *, pdf_bytes: Optional[bytes] = None) -> dict[str, Any]:
    """สร้างหรืออัปเดต .fromdd — ถ้าไม่ส่ง pdf_bytes จะใช้ form.pdf เดิม"""
    path = Path(path)
    if pdf_bytes is None:
        if not path.is_file() or path.stat().st_size == 0:
            raise JobError("job file not found")
        pdf_bytes = read_job_pdf_bytes(path)
        old = read_job(path)
        if not payload.get("source_doc"):
            payload = dict(payload)
            payload["source_doc"] = old.get("source_doc") or ""
        if not payload.get("title"):
            payload = dict(payload)
            payload["title"] = old.get("title") or path.stem
        if not payload.get("template_name") and old.get("template_name"):
            payload = dict(payload)
            payload["template_name"] = old.get("template_name") or ""
    payload = build_payload(
        title=str(payload.get("title") or ""),
        source_doc=str(payload.get("source_doc") or ""),
        template_name=str(payload.get("template_name") or ""),
        fields=payload.get("fields") or [],
    )
    write_job(path, pdf_bytes, payload)
    return payload


def extract_job_pdf(path: Path) -> Path:
    """แตก form.pdf ไป jobs/.cache/<stem>.pdf สำหรับเปิดหน้า / สร้าง PDF"""
    path = Path(path)
    if not path.is_file():
        raise JobError("job file not found")
    cache_dir = path.parent / CACHE_DIR_NAME
    cache_dir.mkdir(parents=True, exist_ok=True)
    dest = cache_dir / (path.stem + ".pdf")
    try:
        if dest.is_file() and dest.stat().st_size > 0:
            return dest
    except OSError:
        pass
    data = read_job_pdf_bytes(path)
    tmp = dest.with_suffix(".pdf.tmp")
    tmp.write_bytes(data)
    os.replace(tmp, dest)
    return dest


def list_jobs(
    jobs_dir: Path,
    query: str = "",
    *,
    limit: int = HISTORY_LIMIT,
) -> list[dict[str, Any]]:
    jobs_dir = Path(jobs_dir)
    files: list[dict[str, Any]] = []
    if jobs_dir.is_dir():
        for path in jobs_dir.glob("*" + JOB_EXT):
            if path.name.endswith(".tmp"):
                continue
            try:
                st = path.stat()
            except OSError:
                continue
            if st.st_size == 0:
                continue
            stem = path.stem
            files.append({
                "kind": "job",
                "name": path.name,
                "stem": stem,
                "group": form_group(stem),
                "mtime": int(st.st_mtime),
                "size": st.st_size,
                "doc_id": make_job_doc(path.name),
            })
    files.sort(key=lambda d: (-int(d["mtime"]), str(d["name"])))
    q = (query or "").strip().lower()
    if q:
        files = [
            d
            for d in files
            if q in str(d["name"]).lower() or q in str(d["group"]).lower()
        ]
    return files[:limit]
