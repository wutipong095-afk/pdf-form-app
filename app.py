# PDF Form Marker — มาร์คจุดบน PDF แล้วเติมข้อมูลเป็นเลเยอร์ทับ
# รัน local: python app.py  →  http://localhost:5000
from __future__ import annotations

import html
import io
import json
import os
import platform
import re
import secrets
import shutil
import subprocess
import sys
import time
import zipfile
from collections import deque
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from threading import Lock
from typing import Optional

import fitz  # PyMuPDF
from flask import (
    Flask,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from backup_core import (
    create_backup_zip,
    export_template_bytes,
    install_formpack,
    list_formpack_templates,
    restore_backup,
)
from envutil import (
    APP_VERSION,
    BASE,
    env_bool,
    legacy_project_data_dir,
    load_dotenv,
    resolve_data_dir,
    resolve_log_dir,
)
from license_core import (
    DEMO_DOC_NAME,
    activate_license,
    can_fill_document,
    file_sha256,
    license_status,
)
from library_core import (
    MAX_SCAN_DEPTH,
    get_library_root,
    init_scaffold,
    is_lib_doc,
    lib_rel_from_doc,
    load_index,
    make_lib_doc,
    mark_has_template,
    resolve_under_root,
    scan_library,
    search_index,
    set_library_root,
    suggest_default_root,
    touch_last_used,
    tpl_beside_pdf,
)
from logging_setup import get_logger, init_logging

load_dotenv()

DATA_DIR = resolve_data_dir()
LOG_DIR = resolve_log_dir(DATA_DIR)
USERS_DIR = DATA_DIR / "users"
FONTS_DIR = BASE / "fonts"
DEMO_DIR = BASE / "demo"

# โหมดโรงเรียน: ไม่บังคับ login (ค่าเริ่มต้น) — เปิด AUTH_REQUIRED=true สำหรับหลายผู้ใช้
AUTH_REQUIRED = env_bool("AUTH_REQUIRED", False)
LOCAL_USER = (os.environ.get("LOCAL_USER", "local").strip() or "local")

ZOOM = 2.0
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "16"))

log = get_logger("app")

# ฟอนต์ไทยราชการ — TH Sarabun (IT๙ = ตัวเลขไทย) ก่อน แล้วค่อย fallback
FONT_CANDIDATES = [
    os.environ.get("FONT_PATH", ""),  # บังคับ path ได้ผ่าน .env
    str(FONTS_DIR / "THSarabunIT๙.ttf"),
    str(FONTS_DIR / "THSarabun.ttf"),
    str(FONTS_DIR / "THSarabunNew.ttf"),
    str(FONTS_DIR / "NotoSansThai-Regular.ttf"),
    r"C:\Windows\Fonts\THSarabunNew.ttf",
    r"C:\Windows\Fonts\THSarabun.ttf",
    r"C:\Windows\Fonts\LeelawUI.ttf",
    r"C:\Windows\Fonts\leelawui.ttf",
    r"C:\Windows\Fonts\tahoma.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansThai-Regular.ttf",
]


def thai_font():
    for f in FONT_CANDIDATES:
        if f and os.path.exists(f):
            return f
    # เผื่อชื่อไฟล์ต่างเล็กน้อย — หา THSarabun*.ttf ใน fonts/ (ไม่เอา Bold/Italic)
    if FONTS_DIR.is_dir():
        for p in sorted(FONTS_DIR.glob("THSarabun*.ttf")):
            name = p.name.lower()
            if "bold" in name or "italic" in name:
                continue
            return str(p)
    return None


# cache ค่า ascender/descender ต่อไฟล์ฟอนต์ (ใช้คำนวณ baseline)
_FONT_METRICS: dict = {}


def _font_metrics(fontfile: str) -> tuple:
    if fontfile not in _FONT_METRICS:
        f = fitz.Font(fontfile=fontfile)
        _FONT_METRICS[fontfile] = (f.ascender, f.descender)
    return _FONT_METRICS[fontfile]


def insert_thai_text(page, point, text, fontsize, fontfile):
    """วางข้อความด้วย insert_htmlbox ซึ่งทำ Thai shaping (GSUB/GPOS) ให้ —
    วรรณยุกต์ไม่ทับสระบน (สี่ ปั่น น้ำ) ต่างจาก insert_text ที่วาง glyph ดิบ ๆ

    วาง rect ให้ baseline บรรทัดแรกตกที่ point.y พอดี เพื่อให้ตำแหน่งตรงกับ
    insert_text เดิมทุกจุด (เทมเพลตเก่าไม่เคลื่อน)
    """
    asc, desc = _font_metrics(fontfile)
    line_h = asc - desc
    top = point.y - asc * fontsize
    n_lines = text.count("\n") + 1
    rect = fitz.Rect(point.x, top, point.x + 10000, top + fontsize * line_h * n_lines + 2)
    fp = Path(fontfile)
    css = (
        '@font-face {font-family: thf; src: url("%s");} '
        "body {margin: 0; padding: 0;} "
        "p {font-family: thf; font-size: %gpx; margin: 0; padding: 0; "
        "line-height: %g; white-space: pre;}" % (fp.name, fontsize, line_h)
    )
    page.insert_htmlbox(
        rect,
        "<p>%s</p>" % html.escape(text),
        css=css,
        archive=fitz.Archive(str(fp.parent)),
    )


def safe_name(name: str) -> str:
    return re.sub(r"[^\w\-ก-๙]", "_", name or "")


def new_event_id() -> str:
    # รวม milli เพื่อลดโอกาสซ้ำเมื่อ request พร้อมกันในวินาทีเดียวกัน
    now = datetime.now()
    return "E-" + now.strftime("%Y%m%d-%H%M%S") + f"-{now.microsecond // 1000:03d}"


def load_users() -> dict:
    """username -> password hash. จาก USERS_JSON หรือ ADMIN_USER/ADMIN_PASSWORD"""
    raw = os.environ.get("USERS_JSON", "").strip()
    if raw:
        data = json.loads(raw)
        out = {}
        for u, pw in data.items():
            if str(pw).startswith(("pbkdf2:", "scrypt:")):
                out[u] = pw
            else:
                out[u] = generate_password_hash(pw)
        return out

    user = os.environ.get("ADMIN_USER", "admin").strip() or "admin"
    pw = os.environ.get("ADMIN_PASSWORD", "changeme")
    return {user: generate_password_hash(pw)}


USERS = load_users()


def user_root(username: str) -> Path:
    return USERS_DIR / safe_name(username)


def user_paths(username: str) -> dict:
    root = user_root(username)
    paths = {
        "root": root,
        "uploads": root / "uploads",
        "templates": root / "templates_json",
        "output": root / "output",
    }
    for p in paths.values():
        p.mkdir(parents=True, exist_ok=True)
    return paths


def seed_demo_for_user(username: str) -> None:
    """คัดลอก demo PDF + เทมเพลตเข้าโฟลเดอร์ user

    seeded.json จำ hash ของไฟล์ที่แอปเคย seed — ถ้าแอปอัปเดต demo แล้วไฟล์
    ของ user ยังเป็นเวอร์ชัน seed เดิม (ไม่ได้แก้/แทนที่เอง) จะอัปเกรดทับให้
    ไม่งั้น demo เก่าจะไม่ผ่านเช็คต้นฉบับตอนกรอกแบบทดลอง ไฟล์ที่ user แตะเองไม่ทับ"""
    paths = user_paths(username)
    seeded_path = paths["root"] / "seeded.json"
    try:
        seeded = json.loads(seeded_path.read_text(encoding="utf-8"))
        if not isinstance(seeded, dict):
            seeded = {}
    except (OSError, ValueError):
        seeded = {}
    changed = False
    for sub, pattern, dst_dir in (
        ("uploads", "*.pdf", paths["uploads"]),
        ("templates_json", "*.json", paths["templates"]),
    ):
        src_dir = DEMO_DIR / sub
        if not src_dir.is_dir():
            continue
        for src in src_dir.glob(pattern):
            dst = dst_dir / src.name
            src_sha = file_sha256(src)
            rec = f"{sub}/{src.name}"
            if dst.exists():
                try:
                    dst_sha = file_sha256(dst)
                except OSError:
                    continue
                if dst_sha != src_sha and seeded.get(rec) != dst_sha:
                    continue  # user แก้/แทนที่เอง — ไม่แตะ
                if dst_sha != src_sha:
                    shutil.copy2(src, dst)
            else:
                shutil.copy2(src, dst)
            if seeded.get(rec) != src_sha:
                seeded[rec] = src_sha
                changed = True
    if changed:
        seeded_path.write_text(
            json.dumps(seeded, ensure_ascii=False, indent=2), encoding="utf-8"
        )


_SECRET_KEY_WAIT_TRIES = 20
_SECRET_KEY_WAIT_SLEEP = 0.05


def _read_secret_key_file(path: Path) -> Optional[str]:
    try:
        saved = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return saved or None


def _wait_secret_key_file(path: Path) -> Optional[str]:
    for _ in range(_SECRET_KEY_WAIT_TRIES):
        saved = _read_secret_key_file(path)
        if saved:
            return saved
        time.sleep(_SECRET_KEY_WAIT_SLEEP)
    return _read_secret_key_file(path)


def _ensure_secret_key() -> str:
    """คีย์เซสชันร่วมทุก gunicorn worker — O_CREAT|O_EXCL กัน race เขียนคนละคีย์"""
    env_key = os.environ.get("SECRET_KEY", "").strip()
    if env_key and env_key != "replace-with-long-random-string":
        return env_key

    key_path = DATA_DIR / "secret_key"
    if key_path.is_file():
        saved = _wait_secret_key_file(key_path)
        if saved:
            return saved

    generated = secrets.token_hex(32)
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(key_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        existing = _wait_secret_key_file(key_path)
        if existing:
            return existing
        log.error("secret_key file exists but unreadable: %s", key_path)
        return generated
    except OSError:
        log.exception(
            "cannot write secret_key under %s — using in-memory key (sessions reset on restart)",
            DATA_DIR,
        )
        return generated

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(generated + "\n")
    except OSError:
        log.exception("failed writing secret_key — using in-memory key")
        return generated
    return generated


app = Flask(__name__)
# secret_key ตั้งใน create_app() หลัง mkdir + init_logging
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
if os.environ.get("SESSION_COOKIE_SECURE", "").lower() in ("1", "true", "yes"):
    app.config["SESSION_COOKIE_SECURE"] = True


def current_user() -> Optional[str]:
    return session.get("user")


def ensure_local_session() -> str:
    user = current_user()
    if user:
        return user
    session["user"] = LOCAL_USER
    seed_demo_for_user(LOCAL_USER)
    return LOCAL_USER


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not AUTH_REQUIRED:
            ensure_local_session()
            return view(*args, **kwargs)
        if not current_user():
            if (
                request.path.startswith("/api/")
                or request.path.startswith("/page/")
                or request.path.startswith("/download/")
            ):
                return jsonify({"error": "unauthorized"}), 401
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def _bind_host() -> str:
    return os.environ.get("HOST", "127.0.0.1").strip().lower()


def _open_folder_allowed() -> bool:
    """เปิดโฟลเดอร์ได้เฉพาะเครื่อง local — ปิดบน Docker/VPS (HOST=0.0.0.0)"""
    if env_bool("ENABLE_OPEN_FOLDER"):
        return True
    if env_bool("DISABLE_OPEN_FOLDER"):
        return False
    return _bind_host() in ("127.0.0.1", "localhost", "::1")


def _open_in_explorer(path: Path) -> None:
    path = path.resolve()
    path.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


# --- client-log rate limit (ต่อ IP) ---
_CLIENT_LOG_LOCK = Lock()
_CLIENT_LOG_HITS: dict[str, deque[float]] = {}
_CLIENT_LOG_WINDOW = 60.0
_CLIENT_LOG_MAX = 20
_CLIENT_LOG_MAX_KEYS = 256


def _client_log_client_key() -> str:
    """remote_addr เป็นค่าเริ่มต้น — เชื่อ XFF เฉพาะเมื่อ TRUST_X_FORWARDED_FOR"""
    if env_bool("TRUST_X_FORWARDED_FOR"):
        xff = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
        if xff:
            return xff
    return request.remote_addr or "local"


def _client_log_allowed(ip: str) -> bool:
    now = time.time()
    with _CLIENT_LOG_LOCK:
        dead: list[str] = []
        for k, q in _CLIENT_LOG_HITS.items():
            while q and now - q[0] > _CLIENT_LOG_WINDOW:
                q.popleft()
            if not q:
                dead.append(k)
        for k in dead:
            _CLIENT_LOG_HITS.pop(k, None)

        q = _CLIENT_LOG_HITS.setdefault(ip, deque())
        if len(q) >= _CLIENT_LOG_MAX:
            return False
        q.append(now)
        while len(_CLIENT_LOG_HITS) > _CLIENT_LOG_MAX_KEYS:
            candidates = [(k, v) for k, v in _CLIENT_LOG_HITS.items() if k != ip and v]
            if not candidates:
                break
            oldest_ip = min(candidates, key=lambda kv: kv[1][0])[0]
            _CLIENT_LOG_HITS.pop(oldest_ip, None)
        return True


@app.before_request
def _assign_request_event():
    g.event_id = new_event_id()


@app.route("/login", methods=["GET", "POST"])
def login():
    if not AUTH_REQUIRED:
        ensure_local_session()
        return redirect(url_for("index"))
    if current_user():
        return redirect(url_for("index"))
    error = None
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        hashed = USERS.get(username)
        if hashed and check_password_hash(hashed, password):
            session.clear()
            session["user"] = username
            seed_demo_for_user(username)
            log.info("login ok user=%s", username)
            nxt = request.args.get("next") or url_for("index")
            if not nxt.startswith("/"):
                nxt = url_for("index")
            return redirect(nxt)
        log.warning("login failed user=%s", username or "(empty)")
        error = "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง"
    return render_template("login.html", error=error)


@app.post("/logout")
def logout():
    session.clear()
    if not AUTH_REQUIRED:
        return redirect(url_for("index"))
    return redirect(url_for("login"))


@app.get("/")
@login_required
def index():
    return render_template(
        "index.html",
        user=current_user(),
        auth_required=AUTH_REQUIRED,
        app_version=APP_VERSION,
    )


@app.get("/api/me")
@login_required
def me():
    user = current_user()
    paths = user_paths(user)
    return jsonify({
        "user": user,
        "auth_required": AUTH_REQUIRED,
        "open_folder_enabled": _open_folder_allowed(),
        "version": APP_VERSION,
        "paths": {
            "data": str(DATA_DIR),
            "output": str(paths["output"]),
            "logs": str(LOG_DIR),
        },
        "license": license_status(DATA_DIR),
    })


@app.get("/api/license")
@login_required
def get_license():
    return jsonify(license_status(DATA_DIR))


@app.post("/api/license")
@login_required
def post_license():
    data = request.get_json(force=True, silent=True) or {}
    key = (data.get("key") or "").strip()
    if not key:
        return jsonify({"error": "กรุณาใส่คีย์ไลเซนต์"}), 400
    try:
        st = activate_license(DATA_DIR, key)
        log.info(
            "license activated machine=%s… exp=%s",
            (st.get("machine_id") or "")[:4],
            st.get("expires"),
        )
        return jsonify({"ok": True, **st})
    except ValueError as e:
        log.warning("license activate failed: %s", e)
        return jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        # ปัญหา config ฝั่งแอป (public key หาย/ไฟล์รหัสเครื่องเสีย) ไม่ใช่คีย์ผิด
        log.exception("license activate runtime error")
        return jsonify({"error": str(e)}), 500


@app.get("/api/docs")
@login_required
def list_docs():
    paths = user_paths(current_user())
    pdfs = sorted(f.name for f in paths["uploads"].glob("*.pdf"))
    tpls = sorted(f.stem for f in paths["templates"].glob("*.json"))
    return jsonify({
        "pdfs": pdfs,
        "templates": tpls,
        "font": thai_font(),
        "user": current_user(),
        "auth_required": AUTH_REQUIRED,
        "license": license_status(DATA_DIR),
    })


@app.post("/api/upload")
@login_required
def upload():
    if "file" not in request.files:
        return jsonify({"error": "ไม่มีไฟล์"}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "ไม่มีชื่อไฟล์"}), 400
    name = safe_name(os.path.splitext(f.filename)[0]) + ".pdf"
    # กันเขียนทับ demo ทางการด้วยเอกสารอื่น (bypass ไลเซนต์)
    if name.lower() == DEMO_DOC_NAME:
        return jsonify({
            "error": f"ชื่อ {DEMO_DOC_NAME} สงวนไว้สำหรับแบบตัวอย่าง — เปลี่ยนชื่อไฟล์ก่อนอัปโหลด",
        }), 400
    paths = user_paths(current_user())
    try:
        f.save(paths["uploads"] / name)
    except OSError:
        log.exception("upload failed name=%s", name)
        return jsonify({"error": "บันทึกไฟล์ไม่สำเร็จ"}), 500
    log.info("upload ok name=%s", name)
    return jsonify({"ok": True, "name": name})


def _pdf_path(username: str, doc: str) -> Path:
    if is_lib_doc(doc):
        root = get_library_root(DATA_DIR)
        if root is None:
            raise FileNotFoundError("ยังไม่ได้ตั้งโฟลเดอร์รากคลังเอกสาร")
        return resolve_under_root(root, lib_rel_from_doc(doc))
    name = safe_name(doc[:-4] if doc.lower().endswith(".pdf") else doc) + ".pdf"
    return user_paths(username)["uploads"] / name


def _require_library_root() -> Path:
    root = get_library_root(DATA_DIR)
    if root is None:
        raise ValueError("ยังไม่ได้ตั้งโฟลเดอร์รากคลังเอกสาร")
    return root


@app.get("/api/pageinfo/<doc>")
@login_required
def pageinfo(doc):
    # doc อาจเป็น @lib/... (frontend ส่งแบบ encodeURIComponent ทั้งก้อน)
    try:
        path = _pdf_path(current_user(), doc)
    except (ValueError, FileNotFoundError) as e:
        return jsonify({"error": str(e)}), 404
    if not path.exists():
        return jsonify({"error": "not found"}), 404
    if is_lib_doc(doc):
        root = get_library_root(DATA_DIR)
        if root is not None:
            try:
                touch_last_used(root, lib_rel_from_doc(doc))
            except OSError:
                pass
    with fitz.open(path) as d:
        sizes = [{"w": p.rect.width, "h": p.rect.height} for p in d]
    return jsonify({"pages": len(sizes), "sizes": sizes, "zoom": ZOOM})


@app.get("/page/<doc>/<int:pno>.png")
@login_required
def page_png(doc, pno):
    try:
        path = _pdf_path(current_user(), doc)
    except (ValueError, FileNotFoundError) as e:
        return jsonify({"error": str(e)}), 404
    if not path.exists():
        return jsonify({"error": "not found"}), 404
    with fitz.open(path) as d:
        if pno < 0 or pno >= len(d):
            return jsonify({"error": "bad page"}), 404
        pix = d[pno].get_pixmap(matrix=fitz.Matrix(ZOOM, ZOOM))
        buf = pix.tobytes("png")
    return send_file(io.BytesIO(buf), mimetype="image/png")


@app.get("/api/template/<name>")
@login_required
def get_template(name):
    path = user_paths(current_user())["templates"] / (safe_name(name) + ".json")
    if not path.exists():
        return jsonify({"error": "not found"}), 404
    with open(path, encoding="utf-8") as f:
        return jsonify(json.load(f))


@app.post("/api/template/<name>")
@login_required
def save_template(name):
    data = request.get_json(force=True, silent=True) or {}
    # ถ้ากำลังแก้เอกสารในคลัง — บันทึกเป็นชื่อ.tpl.json คู่กับ PDF
    doc = data.get("doc") or ""
    if is_lib_doc(doc):
        try:
            root = _require_library_root()
            pdf = resolve_under_root(root, lib_rel_from_doc(doc))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        if not pdf.is_file():
            return jsonify({"error": "ไม่พบ PDF ในคลัง"}), 404
        path = tpl_beside_pdf(pdf)
        fields = data.get("fields") or []
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        rel = lib_rel_from_doc(doc)
        try:
            mark_has_template(root, rel, True)
        except OSError:
            log.exception("mark_has_template failed rel=%s", rel)
        log.info("library template saved rel=%s fields=%s", rel, len(fields))
        return jsonify({"ok": True, "name": pdf.stem, "library": True})

    path = user_paths(current_user())["templates"] / (safe_name(name) + ".json")
    fields = data.get("fields") or []
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    log.info("template saved name=%s fields=%s", safe_name(name), len(fields))
    return jsonify({"ok": True, "name": safe_name(name)})


@app.get("/api/library")
@login_required
def library_status():
    root = get_library_root(DATA_DIR)
    suggested = str(suggest_default_root())
    if root is None:
        return jsonify({
            "configured": False,
            "root": None,
            "suggested_root": suggested,
            "count": 0,
            "docs": [],
            "open_folder_enabled": _open_folder_allowed(),
        })
    idx = load_index(root)
    return jsonify({
        "configured": True,
        "root": str(root),
        "suggested_root": suggested,
        "count": idx.get("count") or len(idx.get("docs") or []),
        "scanned_at": idx.get("scanned_at"),
        "max_depth": idx.get("max_depth") or MAX_SCAN_DEPTH,
        "docs": idx.get("docs") or [],
        "open_folder_enabled": _open_folder_allowed(),
    })


@app.post("/api/library/root")
@login_required
def library_set_root():
    data = request.get_json(force=True, silent=True) or {}
    raw = (data.get("root") or "").strip()
    if raw.lower() in ("default", "auto", ""):
        raw = str(suggest_default_root())
    try:
        root = set_library_root(DATA_DIR, raw)
        created = init_scaffold(root) if data.get("scaffold", True) else []
        idx = scan_library(root)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except OSError:
        log.exception("library set root failed")
        return jsonify({"error": "ตั้งโฟลเดอร์รากไม่สำเร็จ"}), 500
    count = int(idx.get("count") or 0)
    log.info("library root=%s docs=%s scaffold=%s", root, count, created)
    warn = None
    if count >= 500:
        warn = f"พบ PDF {count} ไฟล์ — คลังใหญ่อาจสแกนช้า ควรเลือกโฟลเดอร์ย่อยที่ใช้งานจริง"
    return jsonify({
        "ok": True,
        "root": str(root),
        "scaffold_created": created,
        "count": count,
        "docs": idx.get("docs") or [],
        "warning": warn,
    })


@app.post("/api/library/scan")
@login_required
def library_scan():
    try:
        root = _require_library_root()
        idx = scan_library(root)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except OSError:
        log.exception("library scan failed")
        return jsonify({"error": "สแกนคลังไม่สำเร็จ"}), 500
    count = int(idx.get("count") or 0)
    log.info("library scan docs=%s", count)
    warn = None
    if count >= 500:
        warn = f"พบ PDF {count} ไฟล์ — คลังใหญ่อาจสแกนช้า"
    return jsonify({
        "ok": True,
        "count": count,
        "docs": idx.get("docs") or [],
        "scanned_at": idx.get("scanned_at"),
        "warning": warn,
    })


@app.get("/api/library/search")
@login_required
def library_search():
    try:
        root = _require_library_root()
    except ValueError as e:
        return jsonify({"error": str(e), "docs": []}), 400
    q = request.args.get("q") or ""
    idx = load_index(root)
    hits = search_index(idx, q)
    return jsonify({"ok": True, "q": q, "docs": hits, "count": len(hits)})


@app.post("/api/library/open")
@login_required
def library_open_explorer():
    if not _open_folder_allowed():
        return jsonify({
            "error": "เปิดโฟลเดอร์ใช้ได้เฉพาะโหมดเครื่องเดียว (localhost) — หรือตั้ง ENABLE_OPEN_FOLDER=true",
        }), 403
    data = request.get_json(force=True, silent=True) or {}
    try:
        root = _require_library_root()
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    rel = (data.get("rel") or "").strip()
    try:
        target = root if not rel else resolve_under_root(root, rel)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if target.is_file():
        # เปิดโฟลเดอร์ที่ไฟล์อยู่ + เลือกไฟล์บน Windows
        folder = target.parent
        try:
            if sys.platform == "win32":
                subprocess.Popen(["explorer", "/select,", str(target)])
            else:
                _open_in_explorer(folder)
        except OSError:
            log.exception("library open file failed")
            return jsonify({"error": "เปิดใน Explorer ไม่สำเร็จ"}), 500
    else:
        try:
            _open_in_explorer(target if target.is_dir() else root)
        except OSError:
            log.exception("library open folder failed")
            return jsonify({"error": "เปิดโฟลเดอร์ไม่สำเร็จ"}), 500
    return jsonify({"ok": True, "path": str(target)})


@app.get("/api/library/template")
@login_required
def library_get_template():
    doc = request.args.get("doc") or ""
    if not is_lib_doc(doc):
        return jsonify({"error": "doc ต้องเป็นเอกสารในคลัง (@lib|...)"}), 400
    try:
        root = _require_library_root()
        pdf = resolve_under_root(root, lib_rel_from_doc(doc))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    path = tpl_beside_pdf(pdf)
    if not path.is_file():
        return jsonify({"error": "not found", "has_template": False}), 404
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    data["has_template"] = True
    data["doc"] = make_lib_doc(lib_rel_from_doc(doc))
    return jsonify(data)


@app.post("/api/fill")
@login_required
def fill():
    data = request.get_json(force=True, silent=True) or {}
    doc_name = data.get("doc") or ""
    fields = data.get("fields") or []
    font = thai_font()
    if not font:
        log.error("fill aborted: Thai font missing")
        return jsonify({"error": "ไม่พบฟอนต์ไทย — ตรวจโฟลเดอร์ fonts/"}), 500

    try:
        src = _pdf_path(current_user(), doc_name)
    except (ValueError, FileNotFoundError) as e:
        return jsonify({"error": str(e)}), 404
    if not src.exists():
        return jsonify({"error": "ไม่พบ PDF"}), 404
    # ตรวจไลเซนต์ด้วยชื่อไฟล์จริง (ไม่ใช้ @lib/... ทั้งก้อน)
    lic_doc = src.name if is_lib_doc(doc_name) else doc_name
    ok, lic_err = can_fill_document(DATA_DIR, lic_doc, src)
    if not ok:
        log.warning("fill blocked by license doc=%s", src.name)
        return jsonify({"error": lic_err, "license_required": True}), 402

    out_base = data.get("outname") or src.stem + f"-{int(time.time())}"
    out_name = safe_name(out_base) + ".pdf"
    out_path = user_paths(current_user())["output"] / out_name

    try:
        with fitz.open(src) as d:
            used = 0
            for fld in fields:
                val = str(fld.get("value") or "").strip()
                if not val:
                    continue
                used += 1
                page = d[int(fld["page"])]
                pt = fitz.Point(float(fld["x"]), float(fld["y"]))
                size = float(fld.get("size", 14))
                try:
                    insert_thai_text(page, pt, val, size, font)
                except Exception:
                    # เผื่อ insert_htmlbox ใช้ไม่ได้ — ยอมให้วรรณยุกต์เพี้ยนดีกว่าเติมไม่ได้เลย
                    page.insert_text(
                        pt, val, fontsize=size, fontname="thaifont", fontfile=font, color=(0, 0, 0)
                    )
            try:
                d.subset_fonts()  # insert_htmlbox ฝังฟอนต์เต็มไฟล์ — ตัดให้เหลือเฉพาะที่ใช้
            except Exception:
                pass
            # garbage=4 รวมฟอนต์ที่ฝังซ้ำกันหลายชุดให้เหลือชุดเดียว (ไฟล์เล็กลงมาก)
            d.save(out_path, garbage=4, deflate=True)
    except Exception:
        eid = getattr(g, "event_id", new_event_id())
        log.exception("fill failed event=%s doc=%s", eid, safe_name(doc_name))
        return jsonify({
            "error": f"สร้าง PDF ไม่สำเร็จ (รหัส {eid})",
            "event_id": eid,
        }), 500

    log.info("fill ok fields=%s out=%s", used, out_name)
    return jsonify({"ok": True, "file": out_name})


@app.get("/download/<name>")
@login_required
def download(name):
    path = user_paths(current_user())["output"] / (
        safe_name(name[:-4] if name.lower().endswith(".pdf") else name) + ".pdf"
    )
    if not path.exists():
        return jsonify({"error": "not found"}), 404
    return send_file(path, as_attachment=False, download_name=path.name)


@app.post("/api/open-folder")
@login_required
def open_folder():
    if not _open_folder_allowed():
        return jsonify({
            "error": "เปิดโฟลเดอร์ใช้ได้เฉพาะโหมดเครื่องเดียว (localhost) — หรือตั้ง ENABLE_OPEN_FOLDER=true",
        }), 403
    data = request.get_json(force=True, silent=True) or {}
    which = (data.get("which") or "").strip().lower()
    user = current_user()
    paths = user_paths(user)
    mapping = {
        "data": DATA_DIR,
        "output": paths["output"],
        "logs": LOG_DIR,
        "uploads": paths["uploads"],
    }
    target = mapping.get(which)
    if target is None:
        return jsonify({"error": "which ต้องเป็น data / output / logs / uploads"}), 400
    try:
        _open_in_explorer(target)
    except OSError:
        log.exception("open-folder failed which=%s", which)
        return jsonify({"error": "เปิดโฟลเดอร์ไม่สำเร็จ"}), 500
    log.info("open-folder which=%s", which)
    return jsonify({"ok": True, "path": str(target)})


@app.post("/api/client-log")
@login_required
def client_log():
    ip = _client_log_client_key()
    if not _client_log_allowed(ip):
        return jsonify({"ok": False, "error": "rate_limited"}), 429
    data = request.get_json(force=True, silent=True) or {}
    level = str(data.get("level") or "error").lower()
    message = str(data.get("message") or "")[:500]
    source = str(data.get("source") or "ui")[:80]
    stack = str(data.get("stack") or "")[:2000]
    eid = str(data.get("event_id") or getattr(g, "event_id", new_event_id()))[:40]
    try:
        suppressed = int(data.get("suppressed") or 0)
    except (TypeError, ValueError):
        suppressed = 0
    if suppressed < 0:
        suppressed = 0
    if not message:
        return jsonify({"error": "message required"}), 400
    extra = (" suppressed=%s" % suppressed) if suppressed else ""
    line = "client-log event=%s source=%s msg=%s%s" % (
        eid,
        source,
        message.replace("\n", " "),
        extra,
    )
    if level in ("warning", "warn"):
        log.warning("%s", line)
    else:
        log.error("%s", line)
        if stack:
            log.error("client-stack event=%s\n%s", eid, stack)
    return jsonify({"ok": True, "event_id": eid})


def _support_report_log_files() -> list[Path]:
    """รวม app.log / errors.log และไฟล์ต่อ-pid (app-1234.log) รวม backup หมุนเวียน"""
    found: dict[str, Path] = {}
    for pattern in (
        "app.log",
        "app.log.*",
        "app-*.log",
        "app-*.log.*",
        "errors.log",
        "errors.log.*",
        "errors-*.log",
        "errors-*.log.*",
    ):
        for fpath in LOG_DIR.glob(pattern):
            if fpath.is_file() and fpath.name not in found:
                found[fpath.name] = fpath
    return sorted(found.values(), key=lambda p: p.name)


@app.post("/api/support-report")
@login_required
def support_report():
    """แพ็ก log ล่าสุดเป็น ZIP ใน memory — ไม่สะสมไฟล์ใน LOG_DIR/reports"""
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    download_name = f"report-{stamp}.zip"

    meta = {
        "version": APP_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "os": platform.platform(),
        "python": sys.version.split()[0],
        "auth_required": AUTH_REQUIRED,
        "user": current_user(),
        "data_dir": str(DATA_DIR),
        "log_dir": str(LOG_DIR),
        "license": license_status(DATA_DIR),
    }
    buf = io.BytesIO()
    try:
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("meta.json", json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
            for fpath in _support_report_log_files():
                zf.write(fpath, arcname=fpath.name)
    except OSError:
        log.exception("support-report zip failed")
        return jsonify({"error": "สร้างไฟล์รายงานไม่สำเร็จ"}), 500

    buf.seek(0)
    log.info("support-report created %s", download_name)
    return send_file(
        buf,
        mimetype="application/zip",
        as_attachment=True,
        download_name=download_name,
    )


@app.post("/api/backup")
@login_required
def api_backup():
    """สำรอง uploads + templates + output + library settings — ไม่มี machine_id/license"""
    user = current_user()
    paths = user_paths(user)
    try:
        buf, filename, meta = create_backup_zip(
            data_dir=DATA_DIR,
            username=user or LOCAL_USER,
            user_root=paths["root"],
            app_version=APP_VERSION,
        )
    except OSError:
        log.exception("backup failed")
        return jsonify({"error": "สร้างไฟล์สำรองไม่สำเร็จ"}), 500
    log.info(
        "backup created user=%s uploads=%s templates=%s output=%s",
        user,
        (meta.get("counts") or {}).get("uploads"),
        (meta.get("counts") or {}).get("templates"),
        (meta.get("counts") or {}).get("output"),
    )
    return send_file(
        buf,
        mimetype="application/zip",
        as_attachment=True,
        download_name=filename,
    )


@app.post("/api/restore")
@login_required
def api_restore():
    """กู้จาก ZIP — mode=merge|replace; ไม่เขียน machine_id/license"""
    mode = (request.form.get("mode") or request.args.get("mode") or "merge").strip().lower()
    if mode not in ("merge", "replace"):
        return jsonify({"error": "mode ต้องเป็น merge หรือ replace"}), 400
    if "file" not in request.files:
        return jsonify({"error": "ไม่มีไฟล์ ZIP"}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "ไม่มีชื่อไฟล์"}), 400
    raw = io.BytesIO(f.read())
    user = current_user()
    paths = user_paths(user)
    try:
        result = restore_backup(
            raw,
            user_root=paths["root"],
            data_dir=DATA_DIR,
            mode=mode,  # type: ignore[arg-type]
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except OSError:
        log.exception("restore failed")
        return jsonify({"error": "กู้คืนไม่สำเร็จ"}), 500
    log.info(
        "restore mode=%s written=%s skipped=%s user=%s",
        mode,
        result.get("written"),
        result.get("skipped"),
        user,
    )
    return jsonify(result)


@app.get("/api/template-export/<name>")
@login_required
def api_template_export(name):
    path = user_paths(current_user())["templates"] / (safe_name(name) + ".json")
    if not path.is_file():
        return jsonify({"error": "ไม่พบเทมเพลต"}), 404
    data, filename = export_template_bytes(path, safe_name(name))
    return send_file(
        io.BytesIO(data),
        mimetype="application/json",
        as_attachment=True,
        download_name=filename,
    )


@app.post("/api/template-import")
@login_required
def api_template_import():
    """นำเข้าเทมเพลตเดี่ยว (.json / .tpl.json)"""
    if "file" not in request.files:
        return jsonify({"error": "ไม่มีไฟล์"}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "ไม่มีชื่อไฟล์"}), 400
    raw_name = f.filename
    stem = os.path.splitext(raw_name)[0]
    if stem.lower().endswith(".tpl"):
        stem = stem[:-4]
    name = safe_name(stem)
    if not name:
        return jsonify({"error": "ชื่อเทมเพลตไม่ถูกต้อง"}), 400
    try:
        payload = json.loads(f.read().decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return jsonify({"error": "ไฟล์ต้องเป็น JSON"}), 400
    if not isinstance(payload, dict):
        return jsonify({"error": "รูปแบบเทมเพลตไม่ถูกต้อง"}), 400
    overwrite = (request.form.get("overwrite") or "").lower() in ("1", "true", "yes")
    path = user_paths(current_user())["templates"] / (name + ".json")
    if path.exists() and not overwrite:
        return jsonify({"error": f"มีเทมเพลต \"{name}\" อยู่แล้ว — ระบุ overwrite=true เพื่อทับ", "name": name}), 409
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log.info("template imported name=%s", name)
    return jsonify({"ok": True, "name": name})


@app.get("/api/formpack")
@login_required
def api_formpack_list():
    pack = BASE / "formpacks" / "v1"
    return jsonify({
        "id": "v1",
        "title": "แพ็กฟอร์มโรงเรียน v1",
        "templates": list_formpack_templates(pack),
        "note_th": "เทมเพลตตัวอย่างตำแหน่งฟิลด์ — ต้องจับคู่กับ PDF จริงของโรงเรียนหลังติดตั้ง",
    })


@app.post("/api/formpack/install")
@login_required
def api_formpack_install():
    data = request.get_json(force=True, silent=True) or {}
    pack_id = data.get("id") or "v1"
    pack = BASE / "formpacks" / str(pack_id)
    overwrite = bool(data.get("overwrite"))
    try:
        result = install_formpack(
            pack,
            user_paths(current_user())["templates"],
            overwrite=overwrite,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except OSError:
        log.exception("formpack install failed")
        return jsonify({"error": "ติดตั้งแพ็กไม่สำเร็จ"}), 500
    log.info(
        "formpack %s installed=%s skipped=%s",
        pack_id,
        result.get("installed"),
        result.get("skipped"),
    )
    return jsonify({"ok": True, "pack": pack_id, **result})


@app.errorhandler(Exception)
def handle_unexpected(exc):
    if isinstance(exc, SystemExit):
        raise exc
    from werkzeug.exceptions import HTTPException

    if isinstance(exc, HTTPException):
        return exc
    eid = getattr(g, "event_id", new_event_id())
    log.exception("Unhandled exception event=%s path=%s", eid, request.path)
    if request.path.startswith("/api/") or request.path.startswith("/page/"):
        return jsonify({
            "error": f"เกิดข้อผิดพลาดภายใน (รหัส {eid})",
            "event_id": eid,
        }), 500
    return (
        f"<h1>เกิดข้อผิดพลาด</h1><p>รหัสเหตุการณ์: <code>{html.escape(eid)}</code></p>"
        "<p>ลองสร้างไฟล์รายงานปัญหาจากเมนูในแอป แล้วส่งให้ผู้ขาย</p>",
        500,
    )


def create_app():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    USERS_DIR.mkdir(parents=True, exist_ok=True)
    init_logging(LOG_DIR)
    app.secret_key = _ensure_secret_key()
    log.info(
        "start version=%s os=%s auth_required=%s open_folder=%s data_dir=%s log_dir=%s",
        APP_VERSION,
        platform.platform(),
        AUTH_REQUIRED,
        _open_folder_allowed(),
        DATA_DIR,
        LOG_DIR,
    )
    if not os.environ.get("DATA_DIR", "").strip() and DATA_DIR == legacy_project_data_dir():
        log.info("using legacy project data dir (./data) — set DATA_DIR to override")
    if env_bool("LICENSE_BYPASS"):
        log.warning("LICENSE_BYPASS is ON — ห้ามใช้บนเครื่องลูกค้า / build ปล่อยจริง")
    if not AUTH_REQUIRED and _bind_host() not in ("127.0.0.1", "localhost", "::1"):
        log.warning(
            "AUTH_REQUIRED is false but HOST=%s — APIs are open without login on the network; "
            "set AUTH_REQUIRED=true or bind 127.0.0.1",
            _bind_host(),
        )
    if not AUTH_REQUIRED:
        seed_demo_for_user(LOCAL_USER)
        log.info("school mode: local user=%s (no login)", LOCAL_USER)
    return app


create_app()


if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "").lower() in ("1", "true", "yes")
    app.run(host=host, port=port, debug=debug)
