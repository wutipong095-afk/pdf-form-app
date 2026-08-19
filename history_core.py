"""งานเก่า — PDF ที่กรอกแล้วในโฟลเดอร์ output ของผู้ใช้

ชื่อไฟล์: {ชื่อฟอร์ม}-{YYYYMMDD-HHMMSS}.pdf  (ไม่ทับงานวันเดียวกัน)
เอกสารในแอปอ้างด้วย @out.{filename}
"""
from __future__ import annotations

import os
import re
import shutil
import time
from pathlib import Path
from typing import Any, Optional

OUT_DOC_PREFIX = "@out."
FILLED_FOLDER_NAME = "งานที่กรอกแล้ว"
FILLED_FOLDER_NAMES = frozenset({FILLED_FOLDER_NAME, "filled"})
HISTORY_LIMIT = 300

_SAFE_STEM = re.compile(r"[^\w\-ก-๙]", re.UNICODE)
_ISO_DATE_SUFFIX = re.compile(r"-\d{4}-\d{2}-\d{2}$")
_STAMP_SUFFIX = re.compile(r"-\d{8}-\d{6}(?:-\d+)?$")


def safe_stem(name: str) -> str:
    return _SAFE_STEM.sub("_", name or "") or "filled"


def is_out_doc(doc: str | None) -> bool:
    return str(doc or "").startswith(OUT_DOC_PREFIX)


def make_out_doc(filename: str) -> str:
    return OUT_DOC_PREFIX + Path(filename).name


def out_filename_from_doc(doc: str) -> str:
    body = str(doc or "")[len(OUT_DOC_PREFIX) :]
    body = body.replace("\\", "/").split("/")[-1]
    if not body:
        raise ValueError("invalid history document id")
    stem = body[:-4] if body.lower().endswith(".pdf") else body
    return safe_stem(stem) + ".pdf"


def form_group(stem: str) -> str:
    """ใบเบิก-20260814-103012 → ใบเบิก"""
    s = stem[:-4] if stem.lower().endswith(".pdf") else stem
    s = _ISO_DATE_SUFFIX.sub("", s)
    s = _STAMP_SUFFIX.sub("", s)
    return s or stem


def _preferred_base(raw: str) -> str:
    s = safe_stem(raw)
    s = _ISO_DATE_SUFFIX.sub("", s)
    s = _STAMP_SUFFIX.sub("", s)
    return s or "filled"


def unique_output_name(output_dir: Path, base: str, *, now: Optional[float] = None) -> str:
    """จองชื่อไฟล์แบบ exclusive — ไม่ทับแม้กดสร้าง PDF พร้อมกัน"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(now if now is not None else time.time()))
    stem = f"{_preferred_base(base)}-{stamp}"
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    for n in range(0, 1000):
        name = f"{stem}.pdf" if n == 0 else f"{stem}-{n}.pdf"
        path = output_dir / name
        try:
            fd = os.open(path, flags)
        except FileExistsError:
            continue
        os.close(fd)
        return name
    raise OSError("could not allocate unique output name")


def list_history(
    output_dir: Path,
    query: str = "",
    *,
    limit: int = HISTORY_LIMIT,
) -> dict[str, Any]:
    output_dir = Path(output_dir)
    files: list[dict[str, Any]] = []
    if output_dir.is_dir():
        for path in output_dir.glob("*.pdf"):
            try:
                st = path.stat()
            except OSError:
                continue
            stem = path.stem
            files.append({
                "kind": "pdf",
                "name": path.name,
                "stem": stem,
                "group": form_group(stem),
                "mtime": int(st.st_mtime),
                "size": st.st_size,
                "doc_id": make_out_doc(path.name),
            })
    files.sort(key=lambda d: (-int(d["mtime"]), str(d["name"])))
    q = (query or "").strip().lower()
    if q:
        files = [
            d
            for d in files
            if q in str(d["name"]).lower() or q in str(d["group"]).lower()
        ]
    truncated = len(files) > limit
    files = files[:limit]
    return {
        "count": len(files),
        "truncated": truncated,
        "files": files,
    }


def archive_filled_beside(src_pdf: Path, filled_pdf: Path) -> Optional[str]:
    """คัดลอกงานที่กรอกแล้วไว้โฟลเดอร์คู่ฟอร์มต้นฉบับ — คืนชื่อไฟล์หรือ None"""
    src_pdf = Path(src_pdf)
    filled_pdf = Path(filled_pdf)
    if not src_pdf.is_file() or not filled_pdf.is_file():
        return None
    dest_dir = src_pdf.parent / FILLED_FOLDER_NAME
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filled_pdf.name
    try:
        if dest.resolve() == filled_pdf.resolve():
            return None
    except OSError:
        return None
    if dest.exists():
        dest = dest_dir / f"{filled_pdf.stem}-{int(time.time())}{filled_pdf.suffix}"
    shutil.copy2(filled_pdf, dest)
    return dest.name
