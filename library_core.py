"""คลังเอกสารที่ผู้ใช้กำหนดโฟลเดอร์รากเอง (CP2)

โครง:
  <root>/
    01-การเงิน/ ...
    .pdfmarker/
      index.json
      settings.json

DATA_DIR/library.json จำ path ราก (แยกจาก AppData ระบบ)
"""
from __future__ import annotations

import base64
import json
import os
import time
from pathlib import Path
from typing import Any, Optional
from urllib.parse import unquote

# doc id: @lib. + base64url(rel) — ทน | / ช่องว่าง ในชื่อไฟล์
LIB_DOC_PREFIX = "@lib."
# รูปแบบเก่า (อ่านได้เพื่อไม่พัง session ค้าง)
_LEGACY_PIPE_PREFIX = "@lib|"
_LEGACY_SLASH_PREFIX = "@lib/"

MAX_SCAN_DEPTH = 3
STARTER_FOLDERS = ("01-การเงิน", "02-พัสดุ", "03-บุคคล")
_SKIP_DIR_NAMES = {".pdfmarker", ".git", "__pycache__", "node_modules"}
_TOUCH_MIN_INTERVAL = 60.0
_touch_cache: dict[str, float] = {}


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    _atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def config_path(data_dir: Path) -> Path:
    return Path(data_dir) / "library.json"


def pdfmarker_dir(root: Path) -> Path:
    return Path(root) / ".pdfmarker"


def index_path(root: Path) -> Path:
    return pdfmarker_dir(root) / "index.json"


def settings_path(root: Path) -> Path:
    return pdfmarker_dir(root) / "settings.json"


def is_lib_doc(doc: str) -> bool:
    d = str(doc or "")
    return (
        d.startswith(LIB_DOC_PREFIX)
        or d.startswith(_LEGACY_PIPE_PREFIX)
        or d.startswith(_LEGACY_SLASH_PREFIX)
    )


def make_lib_doc(rel: str) -> str:
    clean = rel.replace("\\", "/").lstrip("/").encode("utf-8")
    token = base64.urlsafe_b64encode(clean).decode("ascii").rstrip("=")
    return LIB_DOC_PREFIX + token


def lib_rel_from_doc(doc: str) -> str:
    d = str(doc or "")
    if d.startswith(LIB_DOC_PREFIX):
        body = d[len(LIB_DOC_PREFIX) :]
        pad = "=" * (-len(body) % 4)
        try:
            return base64.urlsafe_b64decode(body + pad).decode("utf-8").replace("\\", "/").lstrip("/")
        except (ValueError, UnicodeDecodeError) as e:
            raise ValueError("doc id คลังไม่ถูกต้อง") from e
    if d.startswith(_LEGACY_PIPE_PREFIX):
        return d[len(_LEGACY_PIPE_PREFIX) :].replace("|", "/").replace("\\", "/").lstrip("/")
    if d.startswith(_LEGACY_SLASH_PREFIX):
        return unquote(d[len(_LEGACY_SLASH_PREFIX) :]).replace("\\", "/").lstrip("/")
    return d.replace("\\", "/").lstrip("/")


def get_library_root(data_dir: Path) -> Optional[Path]:
    path = config_path(data_dir)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    raw = (data.get("root") or "").strip()
    if not raw:
        return None
    root = Path(raw).expanduser()
    try:
        root = root.resolve()
    except OSError:
        return None
    if not root.is_dir():
        return None
    return root


def set_library_root(data_dir: Path, root_str: str) -> Path:
    raw = (root_str or "").strip()
    if not raw:
        raise ValueError("กรุณาระบุโฟลเดอร์รากคลังเอกสาร")
    root = Path(raw).expanduser().resolve()
    if not root.exists():
        root.mkdir(parents=True, exist_ok=True)
    if not root.is_dir():
        raise ValueError("path ที่ระบุไม่ใช่โฟลเดอร์")
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    _atomic_write_json(
        config_path(data_dir),
        {"root": str(root), "updated_at": int(time.time())},
    )
    ensure_pdfmarker(root)
    return root


def ensure_pdfmarker(root: Path) -> None:
    d = pdfmarker_dir(root)
    d.mkdir(parents=True, exist_ok=True)
    sp = settings_path(root)
    if not sp.is_file():
        _atomic_write_json(
            sp,
            {"max_depth": MAX_SCAN_DEPTH, "version": 1},
        )
    ip = index_path(root)
    if not ip.is_file():
        _atomic_write_json(ip, {"version": 1, "scanned_at": 0, "docs": []})


def init_scaffold(root: Path) -> list[str]:
    """สร้างโฟลเดอร์เริ่มต้นตามงานโรงเรียน — คืนรายชื่อที่สร้างใหม่"""
    ensure_pdfmarker(root)
    created: list[str] = []
    for name in STARTER_FOLDERS:
        p = root / name
        if not p.exists():
            p.mkdir(parents=True, exist_ok=True)
            created.append(name)
    return created


def _write_index(root: Path, payload: dict[str, Any]) -> None:
    _atomic_write_json(index_path(root), payload)


def load_index(root: Path) -> dict[str, Any]:
    ensure_pdfmarker(root)
    ip = index_path(root)
    try:
        data = json.loads(ip.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"version": 1, "scanned_at": 0, "docs": []}
        if not isinstance(data.get("docs"), list):
            data["docs"] = []
        return data
    except (OSError, ValueError):
        return {"version": 1, "scanned_at": 0, "docs": []}


def resolve_under_root(root: Path, rel: str) -> Path:
    """resolve path ใต้ root — กัน path traversal"""
    root = root.resolve()
    rel_norm = rel.replace("\\", "/").lstrip("/")
    if not rel_norm or ".." in rel_norm.split("/"):
        raise ValueError("path ไม่ถูกต้อง")
    target = (root / rel_norm).resolve()
    try:
        target.relative_to(root)
    except ValueError as e:
        raise ValueError("path อยู่นอกคลังเอกสาร") from e
    return target


def tpl_beside_pdf(pdf_path: Path) -> Path:
    """ชื่อ.pdf → ชื่อ.tpl.json คู่กันในโฟลเดอร์เดียวกัน"""
    return pdf_path.parent / (pdf_path.stem + ".tpl.json")


def _folder_label(rel: str) -> str:
    parts = rel.replace("\\", "/").split("/")
    if len(parts) <= 1:
        return ""
    return "/".join(parts[:-1])


def _depth_ok(rel: str, max_depth: int) -> bool:
    parts = [p for p in rel.replace("\\", "/").split("/") if p]
    return max(0, len(parts) - 1) <= max_depth


def scan_library(root: Path, *, max_depth: int = MAX_SCAN_DEPTH) -> dict[str, Any]:
    """สแกน PDF ใต้ root อัปเดต index — คง tags/last_used จากดัชนีเดิม"""
    root = root.resolve()
    ensure_pdfmarker(root)
    prev = load_index(root)
    prev_by_rel = {
        str(d.get("rel") or ""): d
        for d in prev.get("docs") or []
        if isinstance(d, dict) and d.get("rel")
    }

    docs: list[dict[str, Any]] = []
    now = int(time.time())

    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = str(Path(dirpath).resolve().relative_to(root)).replace("\\", "/")
        if rel_dir == ".":
            depth = 0
        else:
            depth = len([p for p in rel_dir.split("/") if p])
        dirnames[:] = [
            d
            for d in dirnames
            if d not in _SKIP_DIR_NAMES and not d.startswith(".") and depth < max_depth
        ]

        for name in filenames:
            if not name.lower().endswith(".pdf"):
                continue
            full = Path(dirpath) / name
            try:
                rel = str(full.resolve().relative_to(root)).replace("\\", "/")
            except ValueError:
                continue
            if not _depth_ok(rel, max_depth):
                continue
            try:
                st = full.stat()
            except OSError:
                continue
            old = prev_by_rel.get(rel) or {}
            tpl = tpl_beside_pdf(full)
            tags = old.get("tags") if isinstance(old.get("tags"), list) else []
            last_used = old.get("last_used")
            docs.append({
                "rel": rel,
                "name": full.stem,
                "filename": full.name,
                "folder": _folder_label(rel),
                "mtime_ns": st.st_mtime_ns,
                "size": st.st_size,
                "has_template": tpl.is_file(),
                "tags": tags,
                "last_used": last_used,
                "doc_id": make_lib_doc(rel),
            })

    docs.sort(key=lambda d: (d.get("folder") or "", d.get("name") or ""))
    payload = {
        "version": 1,
        "scanned_at": now,
        "root": str(root),
        "max_depth": max_depth,
        "count": len(docs),
        "docs": docs,
    }
    _write_index(root, payload)
    return payload


def touch_last_used(root: Path, rel: str) -> None:
    """อัปเดต last_used แบบ debounce — ไม่เขียนดิสก์ทุก pageinfo"""
    key = str(root.resolve()) + "\0" + rel
    now = time.time()
    prev = _touch_cache.get(key, 0.0)
    if now - prev < _TOUCH_MIN_INTERVAL:
        return
    _touch_cache[key] = now

    idx = load_index(root)
    changed = False
    ts = int(now)
    for d in idx.get("docs") or []:
        if isinstance(d, dict) and d.get("rel") == rel:
            d["last_used"] = ts
            changed = True
            break
    if changed:
        _write_index(root, idx)


def search_index(
    index: dict[str, Any],
    query: str,
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    docs = [d for d in (index.get("docs") or []) if isinstance(d, dict)]
    q = (query or "").strip().lower()
    if not q:
        docs.sort(
            key=lambda d: (
                -(d.get("last_used") or 0),
                (d.get("folder") or ""),
                (d.get("name") or ""),
            )
        )
        return docs[:limit]

    scored: list[tuple[int, dict[str, Any]]] = []
    for d in docs:
        name = str(d.get("name") or "").lower()
        folder = str(d.get("folder") or "").lower()
        filename = str(d.get("filename") or "").lower()
        tags = " ".join(str(t).lower() for t in (d.get("tags") or []))
        hay = f"{name} {folder} {filename} {tags}"
        if q not in hay:
            continue
        score = 0
        if name.startswith(q) or q in name:
            score += 100
        if q in folder:
            score += 40
        if q in tags:
            score += 30
        if d.get("last_used"):
            score += 10
        scored.append((score, d))
    scored.sort(key=lambda x: (-x[0], -(x[1].get("last_used") or 0), x[1].get("name") or ""))
    return [d for _, d in scored[:limit]]


def suggest_default_root() -> Path:
    """แนะนำโฟลเดอร์เริ่มต้นใต้ Documents หรือ home"""
    home = Path.home()
    docs = home / "Documents"
    base = docs if docs.is_dir() else home
    return (base / "PDFFormMarker-คลังเอกสาร").resolve()


def mark_has_template(root: Path, rel: str, has: bool = True) -> None:
    """อัปเดตธง has_template ในดัชนีหลังบันทึก .tpl.json โดยไม่ต้องสแกนทั้งคลัง"""
    idx = load_index(root)
    for d in idx.get("docs") or []:
        if isinstance(d, dict) and d.get("rel") == rel:
            d["has_template"] = has
            _write_index(root, idx)
            return
