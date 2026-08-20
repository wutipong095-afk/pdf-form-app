"""คลังสแนปช็อตฟอร์ม — เก็บ PDF ตาม sha256 ของเนื้อไฟล์ ไม่เก็บซ้ำ

ใบงานหลายร้อยใบที่มาจากฟอร์มเดียวกันใช้ PDF ชุดเดียว และเพราะที่อยู่คือ hash
ของเนื้อไฟล์ ตัวคลังจึงเป็นแคชในตัว ไม่ต้องเทียบ mtime ไม่ต้องมีโฟลเดอร์เงา

เอกสารในแอปอ้างด้วย @form.{sha256}
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from fields_core import FormDataError

FORM_DOC_PREFIX = "@form."
MAX_PDF_BYTES = 64 * 1024 * 1024
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")


def is_form_doc(doc: str | None) -> bool:
    return str(doc or "").startswith(FORM_DOC_PREFIX)


def make_form_doc(sha: str) -> str:
    return FORM_DOC_PREFIX + validate_sha(sha)


def validate_sha(sha: str | None) -> str:
    s = str(sha or "").strip().lower()
    if not _SHA_RE.match(s):
        raise FormDataError("invalid form snapshot id")
    return s


def form_sha_from_doc(doc: str) -> str:
    body = str(doc or "")
    if body.startswith(FORM_DOC_PREFIX):
        body = body[len(FORM_DOC_PREFIX) :]
    return validate_sha(body)


def pdf_path(forms_dir: Path, sha: str) -> Path:
    return Path(forms_dir) / (validate_sha(sha) + ".pdf")


def meta_path(forms_dir: Path, sha: str) -> Path:
    return Path(forms_dir) / (validate_sha(sha) + ".json")


def store_pdf(
    forms_dir: Path,
    pdf_bytes: bytes,
    *,
    source_doc: str = "",
    display_name: str = "",
) -> str:
    """เก็บ PDF แล้วคืน sha256 — ถ้ามีอยู่แล้วไม่เขียนซ้ำ"""
    if not pdf_bytes.startswith(b"%PDF-"):
        raise FormDataError("source is not a PDF")
    if len(pdf_bytes) > MAX_PDF_BYTES:
        raise FormDataError("PDF is too large")
    forms_dir = Path(forms_dir)
    forms_dir.mkdir(parents=True, exist_ok=True)
    sha = hashlib.sha256(pdf_bytes).hexdigest()

    dest = pdf_path(forms_dir, sha)
    if not dest.is_file() or dest.stat().st_size != len(pdf_bytes):
        tmp = dest.with_name(dest.name + ".tmp")
        try:
            tmp.write_bytes(pdf_bytes)
            os.replace(tmp, dest)
        except Exception:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
            raise

    meta = meta_path(forms_dir, sha)
    if not meta.is_file():
        _write_json(meta, {
            "sha256": sha,
            "source_doc": (source_doc or "").strip(),
            "display_name": Path((display_name or "").strip() or "form.pdf").name,
            "bytes": len(pdf_bytes),
            "first_seen": datetime.now(timezone.utc).isoformat(),
        })
    return sha


# hash ของไฟล์ต้นฉบับที่ยังอยู่ — แคชไว้เพราะลิสต์งานเก่าถามซ้ำทุกครั้งที่เปิดแถบ
_LIVE_SHA: dict[tuple[str, int, int], str] = {}


def sha_of_file(path: Path) -> Optional[str]:
    """sha256 ของไฟล์ตอนนี้ — None ถ้าอ่านไม่ได้ (ถูกลบ ย้าย หรือไม่มีสิทธิ์)"""
    path = Path(path)
    try:
        st = path.stat()
    except OSError:
        return None
    key = (str(path), int(st.st_mtime_ns), int(st.st_size))
    hit = _LIVE_SHA.get(key)
    if hit:
        return hit
    if st.st_size > MAX_PDF_BYTES:
        return None
    h = hashlib.sha256()
    try:
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                h.update(chunk)
    except OSError:
        return None
    if len(_LIVE_SHA) > 256:
        _LIVE_SHA.clear()
    sha = h.hexdigest()
    _LIVE_SHA[key] = sha
    return sha


def read_meta(forms_dir: Path, sha: str) -> dict[str, Any]:
    path = meta_path(forms_dir, sha)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def require_pdf(forms_dir: Path, sha: str) -> Path:
    path = pdf_path(forms_dir, sha)
    if not path.is_file() or path.stat().st_size == 0:
        raise FileNotFoundError("form snapshot not found")
    return path


def _write_json(path: Path, data: dict[str, Any]) -> None:
    raw = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    tmp = path.with_name(path.name + ".tmp")
    try:
        tmp.write_text(raw, encoding="utf-8")
        os.replace(tmp, path)
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def list_shas(forms_dir: Path) -> set[str]:
    forms_dir = Path(forms_dir)
    if not forms_dir.is_dir():
        return set()
    out = set()
    for p in forms_dir.glob("*.pdf"):
        if _SHA_RE.match(p.stem):
            out.add(p.stem)
    return out


def collect_garbage(forms_dir: Path, keep: Iterable[str], *, dry_run: bool = False) -> list[str]:
    """ลบสแนปช็อตที่ไม่มีใบงานไหนอ้างถึงแล้ว — คืนรายการ sha ที่ลบ"""
    forms_dir = Path(forms_dir)
    kept = {str(s).lower() for s in keep}
    removed: list[str] = []
    for sha in sorted(list_shas(forms_dir) - kept):
        if dry_run:
            removed.append(sha)
            continue
        try:
            pdf_path(forms_dir, sha).unlink(missing_ok=True)
            meta_path(forms_dir, sha).unlink(missing_ok=True)
        except OSError:
            continue
        removed.append(sha)
    return removed


def snapshot_from_file(
    forms_dir: Path,
    src: Path,
    *,
    source_doc: str = "",
    display_name: Optional[str] = None,
) -> str:
    src = Path(src)
    size = src.stat().st_size
    if size > MAX_PDF_BYTES:
        raise FormDataError("PDF is too large")
    return store_pdf(
        forms_dir,
        src.read_bytes(),
        source_doc=source_doc,
        display_name=display_name if display_name is not None else src.name,
    )
