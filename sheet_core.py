"""ใบงาน — JSON ค่าที่กรอกล้วน ๆ อ้างฟอร์มด้วย sha ของสแนปช็อต

เก็บใต้ data/users/<user>/sheets/ ไม่ใช่โฟลเดอร์ติดตั้ง
ตัว PDF อยู่ในคลังสแนปช็อต (form_store) ใบงานจึงเล็กและออโต้เซฟได้ถี่
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import form_store
from fields_core import FormDataError, first_value, normalize_fields
from history_core import HISTORY_LIMIT, form_group, safe_stem

SHEET_EXT = ".json"
SHEET_KIND = "formdd-sheet"
LEGACY_SHEET_KIND = "fromdd-sheet"  # ใบงานที่เซฟไว้ก่อนเปลี่ยนชื่อ
SHEET_VERSION = 1
MAX_SHEET_BYTES = 4 * 1024 * 1024
MAX_TITLE_LEN = 120

SheetError = FormDataError


def sheet_filename(name: str) -> str:
    body = str(name or "").replace("\\", "/").split("/")[-1]
    if not body:
        raise SheetError("invalid sheet id")
    stem = body[: -len(SHEET_EXT)] if body.lower().endswith(SHEET_EXT) else body
    return safe_stem(stem) + SHEET_EXT


def unique_sheet_name(sheets_dir: Path, base: str, *, now: Optional[float] = None) -> str:
    """จองชื่อใบงานแบบ exclusive — ไม่ทับใบที่สร้างวินาทีเดียวกัน"""
    sheets_dir = Path(sheets_dir)
    sheets_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(now if now is not None else time.time()))
    stem = f"{safe_stem(base) or 'sheet'}-{stamp}"
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    for n in range(0, 1000):
        name = f"{stem}{SHEET_EXT}" if n == 0 else f"{stem}-{n}{SHEET_EXT}"
        path = sheets_dir / name
        try:
            fd = os.open(path, flags)
        except FileExistsError:
            continue
        os.close(fd)
        return name
    raise OSError("could not allocate unique sheet name")


def auto_title(title: str, fields: Any, fallback: str) -> str:
    """ชื่อใบที่คนหาเจอ — ต่อค่าแรกที่ไม่ว่างท้ายชื่อฟอร์ม"""
    base = (title or "").strip() or (fallback or "").strip() or "sheet"
    hint = first_value(fields)
    if hint and hint.lower() not in base.lower():
        base = f"{base} — {hint}"
    return base[:MAX_TITLE_LEN]


def build_payload(
    *,
    title: str,
    form_sha: str,
    source_doc: str,
    template_name: str,
    fields: Any,
    title_base: str = "",
    title_auto: bool = True,
    created_at: str = "",
    printed: Any = None,
) -> dict[str, Any]:
    sha = form_store.validate_sha(form_sha)
    rows = normalize_fields(fields)
    base = (title_base or "").strip()[:MAX_TITLE_LEN] or (title or "").strip()[:MAX_TITLE_LEN] or "sheet"
    # ชื่ออัตโนมัติคิดจาก base + ค่าแรกที่กรอกใหม่ทุกครั้ง ไม่ต่อทับของเดิมจนยาวขึ้นเรื่อย ๆ
    resolved = auto_title(base, rows, base) if title_auto else (
        (title or "").strip()[:MAX_TITLE_LEN] or base
    )
    return {
        "version": SHEET_VERSION,
        "kind": SHEET_KIND,
        "title": resolved,
        "title_base": base,
        "title_auto": bool(title_auto),
        "form_sha": sha,
        "source_doc": (source_doc or "").strip(),
        "template_name": (template_name or "").strip()[:MAX_TITLE_LEN],
        "fields": rows,
        "created_at": (created_at or "").strip() or datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "printed": [str(p)[:200] for p in (printed or [])][-20:],
    }


def read_sheet(path: Path) -> dict[str, Any]:
    path = Path(path)
    try:
        if path.stat().st_size > MAX_SHEET_BYTES:
            raise SheetError("sheet file too large")
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise FileNotFoundError("sheet not found") from e
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        raise SheetError("could not read sheet file") from e
    if not isinstance(data, dict) or data.get("kind") not in (SHEET_KIND, LEGACY_SHEET_KIND):
        raise SheetError("not a FormDD sheet")
    data["fields"] = normalize_fields(data.get("fields") or [])
    data["title"] = str(data.get("title") or "").strip()[:MAX_TITLE_LEN] or "sheet"
    data["title_base"] = str(data.get("title_base") or "").strip()[:MAX_TITLE_LEN]
    data["title_auto"] = bool(data.get("title_auto", True))
    data["form_sha"] = form_store.validate_sha(data.get("form_sha"))
    data["source_doc"] = str(data.get("source_doc") or "").strip()
    data["template_name"] = str(data.get("template_name") or "").strip()[:MAX_TITLE_LEN]
    data["printed"] = [str(p) for p in (data.get("printed") or []) if p][-20:]
    return data


def write_sheet(path: Path, payload: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
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


def save_sheet(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    """สร้างหรืออัปเดตใบงาน — ค่าที่ไม่ส่งมาใช้ของเดิม"""
    path = Path(path)
    old: dict[str, Any] = {}
    if path.is_file() and path.stat().st_size > 0:
        old = read_sheet(path)
    template_name = str(payload.get("template_name") or old.get("template_name") or "")
    title = str(payload.get("title") or "")
    # ตั้งชื่อเองอยู่หรือเปล่า — ส่ง title มาพร้อม rename ถึงจะนับว่าคนตั้งเอง
    title_auto = bool(old.get("title_auto", True))
    if payload.get("rename") and title:
        title_auto = False
    else:
        # ออโต้เซฟส่งชื่อเทมเพลตมาด้วยทุกครั้ง — ห้ามให้มันกลายเป็นชื่อใบ
        title = str(old.get("title") or "")
    body = build_payload(
        title=title,
        title_base=str(
            payload.get("title_base") or old.get("title_base") or template_name or title or ""
        ),
        title_auto=title_auto,
        form_sha=str(payload.get("form_sha") or old.get("form_sha") or ""),
        source_doc=str(payload.get("source_doc") or old.get("source_doc") or ""),
        template_name=template_name,
        fields=payload.get("fields") if payload.get("fields") is not None else old.get("fields"),
        created_at=str(old.get("created_at") or ""),
        printed=payload.get("printed") if payload.get("printed") is not None else old.get("printed"),
    )
    write_sheet(path, body)
    return body


def note_printed(path: Path, out_name: str) -> None:
    """จำว่าใบนี้พิมพ์ออกมาเป็นไฟล์ไหน — ให้ลิสต์งานเก่าโยงกลับได้"""
    try:
        data = read_sheet(path)
    except (SheetError, FileNotFoundError):
        return
    printed = [p for p in (data.get("printed") or []) if p != out_name]
    printed.append(out_name)
    data["printed"] = printed[-20:]
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    try:
        write_sheet(path, data)
    except OSError:
        pass


def referenced_shas(sheets_dir: Path) -> set[str]:
    out: set[str] = set()
    for path in Path(sheets_dir).glob("*" + SHEET_EXT):
        try:
            out.add(read_sheet(path)["form_sha"])
        except (SheetError, FileNotFoundError, OSError):
            continue
    return out


def list_sheets(
    sheets_dir: Path,
    query: str = "",
    *,
    limit: int = HISTORY_LIMIT,
) -> list[dict[str, Any]]:
    sheets_dir = Path(sheets_dir)
    files: list[dict[str, Any]] = []
    if sheets_dir.is_dir():
        for path in sheets_dir.glob("*" + SHEET_EXT):
            try:
                st = path.stat()
                if st.st_size == 0:
                    continue
                data = read_sheet(path)
            except (SheetError, FileNotFoundError, OSError):
                continue
            files.append({
                "kind": "sheet",
                "name": path.name,
                "stem": path.stem,
                "title": data.get("title") or path.stem,
                "group": form_group(str(data.get("template_name") or path.stem)),
                "mtime": int(st.st_mtime),
                "size": st.st_size,
                "doc_id": form_store.make_form_doc(data["form_sha"]),
                "sheet": path.name,
                "form_sha": data["form_sha"],
                "source_doc": data.get("source_doc") or "",
                "printed": bool(data.get("printed")),
                "filled": sum(1 for f in data["fields"] if str(f.get("value") or "").strip()),
                "pins": len(data["fields"]),
            })
    files.sort(key=lambda d: (-int(d["mtime"]), str(d["name"])))
    q = (query or "").strip().lower()
    if q:
        files = [
            d
            for d in files
            if q in str(d["name"]).lower()
            or q in str(d["title"]).lower()
            or q in str(d["group"]).lower()
        ]
    return files[:limit]
