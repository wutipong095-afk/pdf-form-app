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
import threading
import time
import uuid
import zipfile
from collections import deque
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from threading import Lock
from typing import Any, Optional

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
    is_frozen,
    legacy_project_data_dir,
    load_dotenv,
    resolve_data_dir,
    resolve_log_dir,
)
from i18n_core import COOKIE_NAME, get_locale, init_i18n, set_persisted_locale, t
from license_core import (
    DEMO_DOC_NAME,
    activate_license,
    can_fill_document,
    can_open_document,
    file_sha256,
    is_canonical_trial_pdf,
    is_trial_filename,
    license_status,
)
from history_core import (
    HISTORY_LIMIT,
    title_to_filename,
    archive_filled_beside,
    is_out_doc,
    list_history,
    out_filename_from_doc,
    unique_output_name,
)
import form_store
import fromdd_io
import job_core
import sheet_core
import workdir_core
from fields_core import FormDataError, layout_fields
from form_store import form_sha_from_doc, is_form_doc, make_form_doc
from sheet_core import list_sheets, save_sheet, sheet_filename, unique_sheet_name
from profiles_core import (
    ProfilesUnreadable,
    create_profile,
    delete_profile,
    load_profiles,
    profiles_path,
    update_profile,
)
from library_core import (
    MAX_SCAN_DEPTH,
    browse_folder_dialog,
    get_library_root,
    init_scaffold,
    is_lib_doc,
    lib_rel_from_doc,
    load_index,
    make_lib_doc,
    mark_has_template,
    maybe_seed_demo_pdf,
    resolve_under_root,
    scan_library,
    search_index,
    set_library_root,
    suggest_default_root,
    touch_last_used,
    tpl_beside_pdf,
)
from logging_setup import get_logger, init_logging
from update_core import UpdateInstallError, check_for_update, download_and_verify_setup

load_dotenv()

DATA_DIR = resolve_data_dir()
LOG_DIR = resolve_log_dir(DATA_DIR)
USERS_DIR = DATA_DIR / "users"
FONTS_DIR = BASE / "fonts"
DEMO_DIR = BASE / "demo"
init_i18n(DATA_DIR)

# โหมดโรงเรียน: ไม่บังคับ login (ค่าเริ่มต้น) — เปิด AUTH_REQUIRED=true สำหรับหลายผู้ใช้
AUTH_REQUIRED = env_bool("AUTH_REQUIRED", False)
LOCAL_USER = (os.environ.get("LOCAL_USER", "local").strip() or "local")

ZOOM = 2.0
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "16"))
MAX_PDF_PAGES = int(os.environ.get("MAX_PDF_PAGES", "500"))

log = get_logger("app")

# ฟอนต์ไทยราชการ — TH Sarabun (เลขอาราบิก) ก่อน
# IT๙ แมป glyph ของ 0-9 เป็นตัวเลขไทย จึงใช้เมื่อตั้ง FONT_PATH เองเท่านั้น
FONT_CANDIDATES = [
    os.environ.get("FONT_PATH", ""),  # บังคับ path ได้ผ่าน .env
    str(FONTS_DIR / "THSarabun.ttf"),
    str(FONTS_DIR / "THSarabunNew.ttf"),
    str(FONTS_DIR / "NotoSansThai-Regular.ttf"),
    r"C:\Windows\Fonts\THSarabunNew.ttf",
    r"C:\Windows\Fonts\THSarabun.ttf",
    r"C:\Windows\Fonts\LeelawUI.ttf",
    r"C:\Windows\Fonts\leelawui.ttf",
    r"C:\Windows\Fonts\tahoma.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansThai-Regular.ttf",
    str(FONTS_DIR / "THSarabunIT๙.ttf"),  # fallback สุดท้าย (ตัวเลขไทย)
]


def _is_it9_font(name: str) -> bool:
    n = name.lower()
    return "it๙" in n or "it9" in n


def thai_font():
    for f in FONT_CANDIDATES:
        if f and os.path.exists(f):
            return f
    # เผื่อชื่อไฟล์ต่างเล็กน้อย — หา THSarabun*.ttf ใน fonts/ (ไม่เอา Bold/Italic)
    # เลขอาราบิกก่อน — ข้าม IT๙ จนกว่าจะไม่มีตัวเลือกอื่น
    if FONTS_DIR.is_dir():
        regular, it9 = [], []
        for p in FONTS_DIR.glob("THSarabun*.ttf"):
            name = p.name.lower()
            if "bold" in name or "italic" in name:
                continue
            (it9 if _is_it9_font(name) else regular).append(p)
        for group in (regular, it9):
            if group:
                return str(sorted(group, key=lambda x: x.name.lower())[0])
    return None


# cache ค่า ascender/descender ต่อไฟล์ฟอนต์ (ใช้คำนวณ baseline)
_FONT_METRICS: dict = {}


_DEFAULT_FILL_METRICS = {"font_ascender": 0.85, "font_descender": -0.25}


def _font_metrics(fontfile: str) -> tuple:
    if fontfile not in _FONT_METRICS:
        f = fitz.Font(fontfile=fontfile)
        _FONT_METRICS[fontfile] = (f.ascender, f.descender)
    return _FONT_METRICS[fontfile]


def fill_font_rev() -> str:
    """fingerprint ของไฟล์ฟอนต์ — ใส่ใน URL พรีวิวกันแคช TTF เก่า"""
    path = thai_font()
    if not path:
        return "0"
    try:
        st = os.stat(path)
    except OSError:
        return "0"
    return f"{int(st.st_mtime)}-{st.st_size}"


def fill_font_metrics() -> dict[str, float]:
    """สัดส่วน baseline ของฟอนต์ที่ใช้ตอนพิมพ์ — พรีวิวต้องใช้ค่าเดียวกัน

    ห้ามโยนต่อเมื่อเปิดฟอนต์ไม่ได้ — /api/docs และ /api/pageinfo ต้องยังเปิดเอกสารได้
    """
    path = thai_font()
    if not path:
        return dict(_DEFAULT_FILL_METRICS)
    try:
        asc, desc = _font_metrics(path)
    except Exception:
        log.warning("fill font metrics unavailable path=%s", path, exc_info=True)
        return dict(_DEFAULT_FILL_METRICS)
    return {"font_ascender": float(asc), "font_descender": float(desc)}


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
ADMIN_USERS = {
    u.strip()
    for u in os.environ.get(
        "ADMIN_USERS", os.environ.get("ADMIN_USER", "admin")
    ).split(",")
    if u.strip()
}


def user_root(username: str) -> Path:
    return USERS_DIR / safe_name(username)


def user_paths(username: str) -> dict:
    root = user_root(username)
    root.mkdir(parents=True, exist_ok=True)
    # งานของผู้ใช้ย้ายไปโฟลเดอร์ที่เลือกเองได้ ส่วนที่เหลืออยู่ใต้โฟลเดอร์ข้อมูลเสมอ
    work = workdir_core.resolve(root)
    paths = {
        "root": root,
        "work": work,
        "uploads": root / "uploads",
        "templates": root / "templates_json",
        "jobs": root / "jobs",
        "output": work / "output",
        "sheets": work / "sheets",
        "forms": work / "forms",
    }
    for p in paths.values():
        p.mkdir(parents=True, exist_ok=True)
    # ย้าย .fromdd ของรุ่นก่อนมาเป็นใบงาน — กันด้วยไฟล์หมาย ทำครั้งเดียวต่อผู้ใช้
    fromdd_io.ensure_migrated(paths["jobs"], paths["sheets"], paths["forms"])
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


app = Flask(
    __name__,
    template_folder=str(BASE / "templates"),
    static_folder=str(BASE / "static"),
)
# secret_key ตั้งใน create_app() หลัง mkdir + init_logging
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
if os.environ.get("SESSION_COOKIE_SECURE", "").lower() in ("1", "true", "yes"):
    app.config["SESSION_COOKIE_SECURE"] = True


@app.context_processor
def inject_i18n():
    loc = get_locale()

    def _t(key: str, **kwargs: Any) -> str:
        return t(key, locale=loc, **kwargs)

    return {"t": _t, "ui_lang": loc}


@app.post("/api/ui-lang")
def api_ui_lang():
    data = request.get_json(force=True, silent=True) or {}
    loc = set_persisted_locale(data.get("lang") or request.args.get("lang") or get_locale())
    resp = jsonify({"ok": True, "lang": loc})
    resp.set_cookie(
        COOKIE_NAME,
        loc,
        max_age=365 * 24 * 3600,
        samesite="Lax",
        httponly=False,
    )
    return resp


def current_user() -> Optional[str]:
    return session.get("user")


def _csrf_token() -> str:
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


def _is_admin() -> bool:
    return not AUTH_REQUIRED or current_user() in ADMIN_USERS


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


def machine_admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not _is_admin():
            return jsonify({"error": "forbidden: admin required"}), 403
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
_LOGIN_WINDOW = 300.0
_LOGIN_MAX = 10
_LOGIN_HITS: dict[str, deque[float]] = {}


def _client_log_client_key() -> str:
    """remote_addr เป็นค่าเริ่มต้น — เชื่อ XFF เฉพาะเมื่อ TRUST_X_FORWARDED_FOR"""
    if env_bool("TRUST_X_FORWARDED_FOR"):
        xff = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
        if xff:
            return xff
    return request.remote_addr or "local"


def _login_attempt_allowed(ip: str) -> bool:
    now = time.time()
    with _CLIENT_LOG_LOCK:
        q = _LOGIN_HITS.setdefault(ip, deque())
        while q and now - q[0] > _LOGIN_WINDOW:
            q.popleft()
        if len(q) >= _LOGIN_MAX:
            return False
        q.append(now)
        return True


def _clear_login_attempts(ip: str) -> None:
    with _CLIENT_LOG_LOCK:
        _LOGIN_HITS.pop(ip, None)


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
    if _bind_host() in ("127.0.0.1", "localhost", "::1"):
        host = (request.host or "").lower()
        if not (
            host in ("127.0.0.1", "localhost", "[::1]")
            or host.startswith("127.0.0.1:")
            or host.startswith("localhost:")
            or host.startswith("[::1]:")
        ):
            return jsonify({"error": "invalid host"}), 400
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        supplied = request.headers.get("X-CSRF-Token") or request.form.get("_csrf_token")
        expected = session.get("_csrf_token")
        if not expected or not supplied or not secrets.compare_digest(expected, supplied):
            return jsonify({"error": "invalid csrf token"}), 403


@app.after_request
def _security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; "
        "frame-ancestors 'none'; form-action 'self'",
    )
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault("Cache-Control", "no-store")
    if request.is_secure:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
    return response


@app.route("/login", methods=["GET", "POST"])
def login():
    if not AUTH_REQUIRED:
        ensure_local_session()
        return redirect(url_for("index"))
    if current_user():
        return redirect(url_for("index"))
    error = None
    if request.method == "POST":
        client_key = _client_log_client_key()
        if not _login_attempt_allowed(client_key):
            return render_template(
                "login.html",
                error=t("login.tooMany"),
                csrf_token=_csrf_token(),
            ), 429
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        hashed = USERS.get(username)
        if hashed and check_password_hash(hashed, password):
            session.clear()
            session["user"] = username
            _csrf_token()
            _clear_login_attempts(client_key)
            seed_demo_for_user(username)
            log.info("login ok user=%s", username)
            nxt = request.args.get("next") or url_for("index")
            if not nxt.startswith("/") or nxt.startswith("//"):
                nxt = url_for("index")
            return redirect(nxt)
        log.warning("login failed user=%s", username or "(empty)")
        error = t("login.badCredentials")
    return render_template("login.html", error=error, csrf_token=_csrf_token())


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
        csrf_token=_csrf_token(),
        fill_font_rev=fill_font_rev(),
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
        "csrf_token": _csrf_token(),
        "is_admin": _is_admin(),
        "paths": {
            "data": str(DATA_DIR),
            "output": str(paths["output"]),
            "logs": str(LOG_DIR),
        },
        "license": license_status(DATA_DIR),
    })


@app.get("/api/update-check")
@login_required
def update_check():
    """เช็กเวอร์ชันจาก latest.json — เน็ตไม่ได้ก็ตอบ offline แล้วใช้แอปต่อได้"""
    force = (request.args.get("force") or "").strip().lower() in ("1", "true", "yes")
    try:
        info = check_for_update(force=force)
    except Exception:
        log.exception("update-check failed")
        return jsonify({
            "current": APP_VERSION,
            "update_available": False,
            "disabled": False,
            "offline": True,
            "latest": None,
            "setup_url": None,
            "sha256": None,
            "size": None,
            "notes": None,
        })
    return jsonify(info)


_UPDATE_INSTALL_ERRORS = {
    "no_feed": "api.updateNoFeed",
    "offline": "api.updateOffline",
    "no_update": "api.updateNoUpdate",
    "no_setup_url": "api.updateNoUrl",
    "no_sha256": "api.updateNoHash",
    "bad_filename": "api.updateBadFile",
    "download_fail": "api.updateDownloadFail",
    "hash_mismatch": "api.updateHashMismatch",
    "size_mismatch": "api.updateSizeMismatch",
    "too_large": "api.updateTooLarge",
}


@app.post("/api/update-install")
@login_required
def update_install():
    """ดาวน์โหลด Setup แล้วตรวจ SHA-256 ก่อนเปิด — เฉพาะเครื่อง local หลังผู้ใช้กดปุ่ม"""
    if not _open_folder_allowed():
        return jsonify({"error": t("api.updateLocalOnly")}), 403
    try:
        result = download_and_verify_setup(DATA_DIR / "updates")
        path = Path(result["path"])
        if sys.platform == "win32":
            os.startfile(str(path))  # type: ignore[attr-defined]
            result["launched"] = True
        else:
            result["launched"] = False
        log.info("update-install version=%s sha256=%s…", result.get("version"), (result.get("sha256") or "")[:12])
        return jsonify(result)
    except UpdateInstallError as exc:
        key = _UPDATE_INSTALL_ERRORS.get(exc.code, "api.updateDownloadFail")
        return jsonify({"ok": False, "error": t(key), "code": exc.code}), 400
    except OSError:
        log.exception("update-install failed")
        return jsonify({"ok": False, "error": t("api.updateDownloadFail")}), 500


@app.get("/api/license")
@login_required
def get_license():
    return jsonify(license_status(DATA_DIR))


@app.post("/api/license")
@machine_admin_required
def post_license():
    data = request.get_json(force=True, silent=True) or {}
    key = (data.get("key") or "").strip()
    if not key:
        return jsonify({"error": t("api.needLicenseKey")}), 400
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


def _license_required_response(message: str):
    return jsonify({"error": message, "license_required": True}), 402


def _paid_license() -> bool:
    return bool(license_status(DATA_DIR).get("licensed"))


@app.get("/api/docs")
@login_required
def list_docs():
    paths = user_paths(current_user())
    pdfs = sorted(f.name for f in paths["uploads"].glob("*.pdf"))
    tpls = sorted(f.stem for f in paths["templates"].glob("*.json"))
    st = license_status(DATA_DIR)
    if not st.get("licensed"):
        allowed = []
        for name in pdfs:
            path = paths["uploads"] / name
            try:
                if is_canonical_trial_pdf(path):
                    allowed.append(name)
            except (RuntimeError, OSError):
                continue
        pdfs = allowed
        trial_tpls = {p.stem for p in (DEMO_DIR / "templates_json").glob("*.json")}
        tpls = [name for name in tpls if name in trial_tpls]
    payload = {
        "pdfs": pdfs,
        "templates": tpls,
        "font": thai_font(),
        "user": current_user(),
        "auth_required": AUTH_REQUIRED,
        "license": st,
    }
    payload.update(fill_font_metrics())
    return jsonify(payload)


@app.post("/api/upload")
@login_required
def upload():
    if not _paid_license():
        return _license_required_response(t("api.uploadNeedsLicense"))
    if "file" not in request.files:
        return jsonify({"error": t("api.noFile")}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": t("api.noFilename")}), 400
    name = safe_name(os.path.splitext(f.filename)[0]) + ".pdf"
    # กันเขียนทับแพ็กทดลองทางการด้วยเอกสารอื่น
    if is_trial_filename(name):
        return jsonify({
            "error": t("api.demoNameReserved", name=name),
        }), 400
    raw = f.read()
    if not raw.startswith(b"%PDF-"):
        return jsonify({"error": "The upload must be a valid PDF file"}), 400
    try:
        with fitz.open(stream=raw, filetype="pdf") as pdf:
            if pdf.needs_pass:
                return jsonify({"error": "Password-protected PDFs are not supported"}), 400
            if len(pdf) < 1 or len(pdf) > MAX_PDF_PAGES:
                return jsonify({"error": f"PDF must contain 1-{MAX_PDF_PAGES} pages"}), 400
    except Exception:
        return jsonify({"error": "The PDF failed validation"}), 400
    paths = user_paths(current_user())
    try:
        (paths["uploads"] / name).write_bytes(raw)
    except OSError:
        log.exception("upload failed name=%s", name)
        return jsonify({"error": t("api.saveUploadFail")}), 500
    log.info("upload ok name=%s", name)
    return jsonify({"ok": True, "name": name})


def _sheet_file(username: str, name: str) -> Path:
    path = user_paths(username)["sheets"] / sheet_filename(name)
    if not path.is_file() or path.stat().st_size == 0:
        raise FileNotFoundError(t("api.sheetMissing"))
    return path


def _license_name_for_source(source_doc: str, fallback: str) -> str:
    src = (source_doc or "").strip()
    if not src or is_form_doc(src) or is_out_doc(src):
        return fallback
    if is_lib_doc(src):
        try:
            return Path(lib_rel_from_doc(src)).name
        except ValueError:
            return fallback
    return Path(src).name


def _pdf_path(username: str, doc: str) -> Path:
    if is_form_doc(doc):
        # สแนปช็อตเก็บตาม sha ของเนื้อไฟล์ — เปิดตรง ๆ ไม่ต้องแตกแคช
        return form_store.require_pdf(user_paths(username)["forms"], form_sha_from_doc(doc))
    if is_out_doc(doc):
        return user_paths(username)["output"] / out_filename_from_doc(doc)
    if is_lib_doc(doc):
        root = get_library_root(DATA_DIR)
        if root is None:
            raise FileNotFoundError(t("api.libRootNotSet"))
        return resolve_under_root(root, lib_rel_from_doc(doc))
    name = safe_name(doc[:-4] if doc.lower().endswith(".pdf") else doc) + ".pdf"
    return user_paths(username)["uploads"] / name


def _resolve_open_pdf(username: str, doc: str) -> tuple[Path, str]:
    """PDF ที่เปิดได้ + ชื่อไฟล์สำหรับเช็คไลเซนต์ (สแนปช็อตใช้ชื่อต้นฉบับที่บันทึกไว้)"""
    path = _pdf_path(username, doc)
    if is_form_doc(doc):
        meta = form_store.read_meta(user_paths(username)["forms"], form_sha_from_doc(doc))
        fallback = str(meta.get("display_name") or path.name)
        return path, _license_name_for_source(str(meta.get("source_doc") or ""), fallback)
    if is_lib_doc(doc):
        return path, path.name
    return path, Path(str(doc or path.name)).name


def _require_library_root() -> Path:
    root = get_library_root(DATA_DIR)
    if root is None:
        raise ValueError(t("api.libRootNotSet"))
    return root


@app.get("/api/pageinfo/<doc>")
@login_required
def pageinfo(doc):
    # doc อาจเป็น @lib/... (frontend ส่งแบบ encodeURIComponent ทั้งก้อน)
    try:
        path, lic_doc = _resolve_open_pdf(current_user(), doc)
    except (ValueError, FileNotFoundError, FormDataError) as e:
        return jsonify({"error": str(e)}), 404
    if not path.exists():
        return jsonify({"error": "not found"}), 404
    ok, lic_err = can_open_document(DATA_DIR, lic_doc, path)
    if not ok:
        return _license_required_response(lic_err)
    if is_lib_doc(doc):
        root = get_library_root(DATA_DIR)
        if root is not None:
            try:
                touch_last_used(root, lib_rel_from_doc(doc))
            except OSError:
                pass
    with fitz.open(path) as d:
        sizes = [{"w": p.rect.width, "h": p.rect.height} for p in d]
    info = {"pages": len(sizes), "sizes": sizes, "zoom": ZOOM}
    info.update(fill_font_metrics())
    return jsonify(info)


@app.get("/api/fill-font")
@login_required
def fill_font_file():
    """TTF เดียวกับตอนสร้าง PDF — ให้ overlay พรีวิวใช้ฟอนต์เดียวกัน"""
    path = thai_font()
    if not path or not os.path.isfile(path):
        return jsonify({"error": t("api.thaiFontMissing")}), 404
    resp = send_file(path, mimetype="font/ttf", download_name="fill.ttf", as_attachment=False)
    # URL มี ?v=mtime-size จากหน้า index — แคชได้เมื่อไฟล์เดิม, เปลี่ยนฟอนต์แล้ว URL ใหม่
    resp.headers["Cache-Control"] = "private, max-age=86400"
    return resp


@app.get("/page/<doc>/<int:pno>.png")
@login_required
def page_png(doc, pno):
    try:
        path, lic_doc = _resolve_open_pdf(current_user(), doc)
    except (ValueError, FileNotFoundError, FormDataError) as e:
        return jsonify({"error": str(e)}), 404
    if not path.exists():
        return jsonify({"error": "not found"}), 404
    ok, lic_err = can_open_document(DATA_DIR, lic_doc, path)
    if not ok:
        return _license_required_response(lic_err)
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
    doc = data.get("doc") or ""
    if is_form_doc(doc) or is_out_doc(doc):
        return jsonify({"error": t("api.tplFromSheet")}), 400
    try:
        data = dict(data)
        data["fields"] = layout_fields(data.get("fields") or [])
    except FormDataError as e:
        return jsonify({"error": str(e)}), 400
    # ถ้ากำลังแก้เอกสารในคลัง — บันทึกเป็นชื่อ.tpl.json คู่กับ PDF
    if is_lib_doc(doc):
        if not _paid_license():
            return _license_required_response(t("api.libraryNeedsLicense"))
        try:
            root = _require_library_root()
            pdf = resolve_under_root(root, lib_rel_from_doc(doc))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        if not pdf.is_file():
            return jsonify({"error": t("api.libPdfMissing")}), 404
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


# --- สมุดข้อมูลล่วงหน้า (autofill profiles) ---
_PROFILE_ID_RE = re.compile(r"^p-[0-9a-f]{4,32}$")


def _profiles_root() -> Path:
    return user_paths(current_user())["root"]


def _clean_profile_id(profile_id: str) -> Optional[str]:
    pid = (profile_id or "").strip()
    return pid if _PROFILE_ID_RE.match(pid) else None


def _profiles_unreadable_response(exc: ProfilesUnreadable):
    """ไฟล์สมุดเสีย — บอกที่อยู่ไฟล์ แล้วปฏิเสธทุกการเขียน (กันเขียนทับของเดิม)"""
    path = profiles_path(_profiles_root())
    log.error("profiles.json unreadable path=%s err=%s", path, exc)
    return jsonify({
        "error": t("profiles.unreadable", path=str(path)),
        "unreadable": True,
    }), 409


@app.get("/api/profiles")
@login_required
def profiles_list():
    try:
        return jsonify(load_profiles(_profiles_root()))
    except ProfilesUnreadable as e:
        return _profiles_unreadable_response(e)


@app.post("/api/profiles")
@login_required
def profiles_create():
    data = request.get_json(force=True, silent=True)
    try:
        profile = create_profile(_profiles_root(), data)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except ProfilesUnreadable as e:
        return _profiles_unreadable_response(e)
    log.info("profile created id=%s keys=%s", profile["id"], len(profile["values"]))
    return jsonify({"ok": True, "profile": profile})


@app.put("/api/profiles/<profile_id>")
@login_required
def profiles_update(profile_id):
    pid = _clean_profile_id(profile_id)
    if not pid:
        return jsonify({"error": t("profiles.notFound")}), 404
    data = request.get_json(force=True, silent=True)
    try:
        profile = update_profile(_profiles_root(), pid, data)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except ProfilesUnreadable as e:
        return _profiles_unreadable_response(e)
    except KeyError:
        return jsonify({"error": t("profiles.notFound")}), 404
    log.info("profile updated id=%s keys=%s", pid, len(profile["values"]))
    return jsonify({"ok": True, "profile": profile})


@app.delete("/api/profiles/<profile_id>")
@login_required
def profiles_delete(profile_id):
    pid = _clean_profile_id(profile_id)
    if not pid:
        return jsonify({"error": t("profiles.notFound")}), 404
    try:
        delete_profile(_profiles_root(), pid)
    except ProfilesUnreadable as e:
        return _profiles_unreadable_response(e)
    except KeyError:
        return jsonify({"error": t("profiles.notFound")}), 404
    log.info("profile deleted id=%s", pid)
    return jsonify({"ok": True})


@app.get("/api/library")
@login_required
def library_status():
    if not _paid_license():
        return _license_required_response(t("api.libraryNeedsLicense"))
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


def _library_demo_pdf() -> Path:
    return DEMO_DIR / "uploads" / DEMO_DOC_NAME


def _scan_library_with_demo(root: Path, *, allow_seed: bool = False) -> tuple[dict, Optional[str]]:
    """สแกนคลัง — seed demo เฉพาะเมื่อ allow_seed (ค่าแนะนำ / scaffold ใหม่)"""
    idx = scan_library(root)
    seeded_rel = None
    if allow_seed and int(idx.get("count") or 0) == 0:
        seeded_rel = maybe_seed_demo_pdf(root, _library_demo_pdf())
        if seeded_rel:
            idx = scan_library(root)
            log.info("library seeded demo rel=%s", seeded_rel)
    return idx, seeded_rel


# ไดอะล็อกเลือกโฟลเดอร์รันนอก waitress worker — client poll ผล
_BROWSE_LOCK = Lock()
_BROWSE_JOBS: dict[str, dict[str, Any]] = {}
_BROWSE_ACTIVE = False


def _browse_job_cleanup(max_age_s: float = 600.0) -> None:
    now = time.time()
    dead = [k for k, v in _BROWSE_JOBS.items() if now - float(v.get("started") or 0) > max_age_s]
    for k in dead:
        _BROWSE_JOBS.pop(k, None)


@app.post("/api/library/browse")
@machine_admin_required
def library_browse():
    """เริ่มเลือกโฟลเดอร์แบบ async — คืน job_id แล้ว poll ที่ GET .../browse/<id>"""
    if not _paid_license():
        return _license_required_response(t("api.libraryNeedsLicense"))
    if not _open_folder_allowed():
        return jsonify({
            "error": t("api.browseLocalOnly"),
        }), 403
    data = request.get_json(force=True, silent=True) or {}
    initial = (data.get("initial") or "").strip()
    if not initial:
        root = get_library_root(DATA_DIR)
        initial = str(root) if root else str(suggest_default_root().parent)

    return _browse_start(initial)


def _browse_start(initial: str):
    """เปิดกล่องเลือกโฟลเดอร์นอก worker แล้วคืน job_id ให้ client มา poll"""
    global _BROWSE_ACTIVE
    with _BROWSE_LOCK:
        _browse_job_cleanup()
        if _BROWSE_ACTIVE:
            return jsonify({"error": t("api.browseBusy")}), 409
        job_id = uuid.uuid4().hex
        _BROWSE_ACTIVE = True
        _BROWSE_JOBS[job_id] = {
            "started": time.time(),
            "done": False,
            "cancelled": False,
            "path": None,
            "error": None,
        }

    def _run(jid: str, init_path: str) -> None:
        global _BROWSE_ACTIVE
        try:
            chosen = browse_folder_dialog(init_path or None)
            with _BROWSE_LOCK:
                job = _BROWSE_JOBS.get(jid)
                if job is not None:
                    job["done"] = True
                    job["cancelled"] = chosen is None
                    job["path"] = chosen
        except Exception as exc:  # noqa: BLE001 — ส่งข้อความให้ client
            log.exception("folder browse failed")
            with _BROWSE_LOCK:
                job = _BROWSE_JOBS.get(jid)
                if job is not None:
                    job["done"] = True
                    job["error"] = t("api.browseDialogFail")
                    job["detail"] = str(exc)
        finally:
            with _BROWSE_LOCK:
                _BROWSE_ACTIVE = False

    threading.Thread(target=_run, args=(job_id, initial), daemon=True).start()
    return jsonify({"ok": True, "job_id": job_id, "pending": True})


def _browse_poll(job_id: str):
    with _BROWSE_LOCK:
        job = _BROWSE_JOBS.get(job_id)
        if job is None:
            return jsonify({"error": t("api.browseJobMissing")}), 404
        if not job.get("done"):
            return jsonify({"ok": True, "pending": True, "job_id": job_id})
        payload = {
            "ok": not job.get("error"),
            "pending": False,
            "job_id": job_id,
            "cancelled": bool(job.get("cancelled")),
            "path": job.get("path"),
            "error": job.get("error"),
        }
        # ลบหลังอ่านครั้งแรก — กัน poll ซ้ำกินหน่วยความจำ
        _BROWSE_JOBS.pop(job_id, None)
    if payload.get("error"):
        return jsonify(payload), 500
    return jsonify(payload)


@app.get("/api/library/browse/<job_id>")
@machine_admin_required
def library_browse_status(job_id: str):
    if not _paid_license():
        return _license_required_response(t("api.libraryNeedsLicense"))
    if not _open_folder_allowed():
        return jsonify({"error": t("api.browseLocalOnly")}), 403
    return _browse_poll(job_id)


@app.get("/api/workdir")
@login_required
def workdir_get():
    return jsonify(workdir_core.status(user_root(current_user())))


@app.post("/api/workdir/browse")
@machine_admin_required
def workdir_browse():
    if not _open_folder_allowed():
        return jsonify({"error": t("api.browseLocalOnly")}), 403
    data = request.get_json(force=True, silent=True) or {}
    initial = (data.get("initial") or "").strip()
    if not initial:
        initial = str(Path.home() / "Documents")
    return _browse_start(initial)


@app.get("/api/workdir/browse/<job_id>")
@machine_admin_required
def workdir_browse_status(job_id: str):
    if not _open_folder_allowed():
        return jsonify({"error": t("api.browseLocalOnly")}), 403
    return _browse_poll(job_id)


@app.post("/api/workdir")
@machine_admin_required
def workdir_set():
    """ย้ายที่เก็บงาน — ใบงานที่มีอยู่ย้ายตามไปด้วย"""
    data = request.get_json(force=True, silent=True) or {}
    root = user_root(current_user())
    try:
        if data.get("reset"):
            out = workdir_core.reset(root)
        else:
            out = workdir_core.set_work_dir(
                root,
                str(data.get("path") or ""),
                # ห้ามชี้เข้าโฟลเดอร์ข้อมูล/ติดตั้งของโปรแกรมเอง
                forbidden=(DATA_DIR, BASE),
            )
    except workdir_core.WorkDirError as e:
        return jsonify({"error": str(e)}), 400
    except OSError as e:
        log.exception("set work dir failed")
        return jsonify({"error": str(e)}), 400
    return jsonify(out)


@app.post("/api/library/root")
@machine_admin_required
def library_set_root():
    if not _paid_license():
        return _license_required_response(t("api.libraryNeedsLicense"))
    data = request.get_json(force=True, silent=True) or {}
    raw = (data.get("root") or "").strip()
    used_default = raw.lower() in ("default", "auto", "")
    if used_default:
        raw = str(suggest_default_root())
    try:
        root = set_library_root(DATA_DIR, raw)
        created = init_scaffold(root) if data.get("scaffold", True) else []
        # seed demo เฉพาะ「ใช้ค่าแนะนำ」— ไม่ใส่ในโฟลเดอร์ว่างที่ผู้ใช้เลือกเอง
        allow_seed = used_default
        idx, seeded_rel = _scan_library_with_demo(root, allow_seed=allow_seed)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except OSError:
        log.exception("library set root failed")
        return jsonify({"error": t("api.setRootFail")}), 500
    count = int(idx.get("count") or 0)
    log.info("library root=%s docs=%s scaffold=%s seed=%s", root, count, created, allow_seed)
    warn = None
    if count >= 500:
        warn = t("api.largeLibWarn", count=count)
    return jsonify({
        "ok": True,
        "root": str(root),
        "scaffold_created": created,
        "seeded_demo": seeded_rel,
        "count": count,
        "docs": idx.get("docs") or [],
        "warning": warn,
    })


@app.post("/api/library/scan")
@machine_admin_required
def library_scan():
    if not _paid_license():
        return _license_required_response(t("api.libraryNeedsLicense"))
    try:
        root = _require_library_root()
        # สแกนอย่างเดียว — ไม่ seed ทับโฟลเดอร์ที่ผู้ใช้ตั้งใจให้ว่าง
        idx, seeded_rel = _scan_library_with_demo(root, allow_seed=False)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except OSError:
        log.exception("library scan failed")
        return jsonify({"error": t("api.scanFail")}), 500
    count = int(idx.get("count") or 0)
    log.info("library scan docs=%s", count)
    warn = None
    if count >= 500:
        warn = t("api.largeLibWarnShort", count=count)
    return jsonify({
        "ok": True,
        "count": count,
        "docs": idx.get("docs") or [],
        "scanned_at": idx.get("scanned_at"),
        "seeded_demo": seeded_rel,
        "warning": warn,
    })


@app.get("/api/library/search")
@login_required
def library_search():
    if not _paid_license():
        return _license_required_response(t("api.libraryNeedsLicense"))
    try:
        root = _require_library_root()
    except ValueError as e:
        return jsonify({"error": str(e), "docs": []}), 400
    q = request.args.get("q") or ""
    idx = load_index(root)
    hits = search_index(idx, q)
    return jsonify({"ok": True, "q": q, "docs": hits, "count": len(hits)})


@app.post("/api/library/open")
@machine_admin_required
def library_open_explorer():
    if not _paid_license():
        return _license_required_response(t("api.libraryNeedsLicense"))
    if not _open_folder_allowed():
        return jsonify({
            "error": t("api.openFolderLocalOnly"),
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
            return jsonify({"error": t("api.openExplorerFail")}), 500
    else:
        try:
            _open_in_explorer(target if target.is_dir() else root)
        except OSError:
            log.exception("library open folder failed")
            return jsonify({"error": t("api.openFolderFail")}), 500
    return jsonify({"ok": True, "path": str(target)})


@app.get("/api/library/template")
@login_required
def library_get_template():
    if not _paid_license():
        return _license_required_response(t("api.libraryNeedsLicense"))
    doc = request.args.get("doc") or ""
    if not is_lib_doc(doc):
        return jsonify({"error": t("api.needLibDoc")}), 400
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


def _sheet_export_dir(paths: dict, max_age_s: float = 600.0) -> Path:
    """ที่พักไฟล์ส่งออก/นำเข้า — กวาดของเก่าทิ้งทุกครั้ง ไม่ให้โตไปเรื่อย ๆ"""
    d = paths["root"] / "export"
    d.mkdir(parents=True, exist_ok=True)
    now = time.time()
    for p in d.iterdir():
        try:
            if p.is_file() and now - p.stat().st_mtime > max_age_s:
                p.unlink()
        except OSError:
            pass
    return d


def _source_label(source_doc: str) -> str:
    """ชื่อฟอร์มต้นฉบับแบบที่คนอ่านรู้เรื่อง — @lib|a/b.pdf → b.pdf"""
    return _license_name_for_source(source_doc, "")


def _live_source_sha(username: str, source_doc: str) -> Optional[str]:
    """sha ของฟอร์มต้นฉบับตอนนี้ — None ถ้าไฟล์หายไปหรือเปิดไม่ได้"""
    src = (source_doc or "").strip()
    if not src or is_form_doc(src) or is_out_doc(src):
        return None
    try:
        return form_store.sha_of_file(_pdf_path(username, src))
    except (ValueError, FileNotFoundError, OSError, FormDataError):
        return None


def _source_state(username: str, source_doc: str, form_sha: str) -> dict:
    """บอกว่าฟอร์มต้นฉบับยังอยู่ไหม และถูกอัปโหลดทับด้วยเวอร์ชันใหม่หรือยัง"""
    live = _live_source_sha(username, source_doc)
    return {
        "source_name": _source_label(source_doc),
        "source_present": live is not None,
        # ทับด้วยไฟล์คนละตัว — ไม่เปลี่ยนให้เอง ต้องให้ผู้ใช้สั่ง
        "source_changed": bool(live and live != form_sha),
    }


def _sheet_response(path: Path, data: Optional[dict] = None) -> dict:
    data = data if data is not None else sheet_core.read_sheet(path)
    return {
        "ok": True,
        "sheet": path.name,
        "doc_id": make_form_doc(data["form_sha"]),
        "title": data.get("title") or path.stem,
        "title_auto": bool(data.get("title_auto", True)),
        "form_sha": data["form_sha"],
        "source_doc": data.get("source_doc") or "",
        "template_name": data.get("template_name") or "",
        "fields": data.get("fields") or [],
        "printed": data.get("printed") or [],
        "updated_at": data.get("updated_at"),
        **_source_state(current_user(), str(data.get("source_doc") or ""), data["form_sha"]),
    }


def _snapshot_for_source(user: str, source_doc: str) -> tuple[str, str]:
    """เก็บฟอร์มต้นฉบับเข้าคลังสแนปช็อต — คืน (sha, ชื่อที่ใช้เช็คไลเซนต์)"""
    src, lic_doc = _resolve_open_pdf(user, source_doc)
    if not src.is_file():
        raise FileNotFoundError(t("api.pdfMissing"))
    ok, lic_err = can_open_document(DATA_DIR, lic_doc, src)
    if not ok:
        raise PermissionError(lic_err)
    sha = form_store.snapshot_from_file(
        user_paths(user)["forms"], src, source_doc=source_doc, display_name=lic_doc
    )
    return sha, lic_doc


@app.post("/api/sheets")
@login_required
def sheets_save():
    data = request.get_json(force=True, silent=True) or {}
    raw_sheet = str(data.get("sheet") or "").strip()
    source_doc = str(data.get("source_doc") or "").strip()
    title = str(data.get("title") or "").strip()
    template_name = str(data.get("template_name") or "").strip()
    fields = data.get("fields") or []
    user = current_user()
    sheets_dir = user_paths(user)["sheets"]

    try:
        if raw_sheet:
            path = sheets_dir / sheet_filename(raw_sheet)
            if not path.is_file() or path.stat().st_size == 0:
                return jsonify({"error": t("api.sheetMissing")}), 404
            body = save_sheet(path, {
                "title": title,
                "template_name": template_name,
                "fields": fields,
            })
            return jsonify(_sheet_response(path, body))

        if not source_doc or is_form_doc(source_doc) or is_out_doc(source_doc):
            return jsonify({"error": t("api.sheetNeedSource")}), 400
        try:
            sha, lic_doc = _snapshot_for_source(user, source_doc)
        except PermissionError as e:
            return _license_required_response(str(e))
        except (ValueError, FileNotFoundError) as e:
            return jsonify({"error": str(e)}), 404

        base = template_name or title or Path(lic_doc).stem
        name = unique_sheet_name(sheets_dir, base)
        path = sheets_dir / name
        try:
            body = save_sheet(path, {
                "title_base": title or base,
                "form_sha": sha,
                "source_doc": source_doc,
                "template_name": template_name,
                "fields": fields,
            })
        except Exception:
            # unique_sheet_name จองชื่อไว้แล้ว — อย่าทิ้งไฟล์ 0 ไบต์ค้างไว้
            try:
                if path.is_file() and path.stat().st_size == 0:
                    path.unlink()
            except OSError:
                pass
            raise
        log.info("sheet created name=%s form=%s fields=%s", name, sha[:12], len(body["fields"]))
        return jsonify(_sheet_response(path, body))
    except FormDataError as e:
        return jsonify({"error": str(e)}), 400


@app.get("/api/sheets/<name>")
@login_required
def sheets_get(name):
    try:
        path = _sheet_file(current_user(), name)
        return jsonify(_sheet_response(path))
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except FormDataError as e:
        return jsonify({"error": str(e)}), 400


@app.delete("/api/sheets/<name>")
@login_required
def sheets_delete(name):
    paths = user_paths(current_user())
    try:
        path = _sheet_file(current_user(), name)
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except FormDataError as e:
        return jsonify({"error": str(e)}), 400
    try:
        path.unlink()
    except OSError as e:
        log.warning("sheet delete failed name=%s err=%s", path.name, e)
        return jsonify({"error": t("api.sheetDeleteFail")}), 500
    freed = form_store.collect_garbage(
        paths["forms"], sheet_core.referenced_shas(paths["sheets"])
    )
    log.info("sheet deleted name=%s snapshots_freed=%s", path.name, len(freed))
    return jsonify({"ok": True, "sheet": path.name, "snapshots_freed": len(freed)})


@app.post("/api/sheets/<name>/duplicate")
@login_required
def sheets_duplicate(name):
    """ทำใบใหม่จากใบนี้ — งานที่ทำบ่อยสุดคือเอาใบเดือนก่อนมาแก้ไม่กี่ช่อง"""
    paths = user_paths(current_user())
    try:
        src = sheet_core.read_sheet(_sheet_file(current_user(), name))
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except FormDataError as e:
        return jsonify({"error": str(e)}), 400
    base = src.get("template_name") or src.get("title") or "sheet"
    new_name = unique_sheet_name(paths["sheets"], base)
    path = paths["sheets"] / new_name
    try:
        body = save_sheet(path, {
            "title": src.get("title") or base,
            "form_sha": src["form_sha"],
            "source_doc": src.get("source_doc") or "",
            "template_name": src.get("template_name") or "",
            "fields": src.get("fields") or [],
        })
    except Exception:
        try:
            if path.is_file() and path.stat().st_size == 0:
                path.unlink()
        except OSError:
            pass
        raise
    log.info("sheet duplicated from=%s to=%s", path.name, new_name)
    return jsonify(_sheet_response(path, body))


@app.post("/api/sheets/<name>/rename")
@login_required
def sheets_rename(name):
    """ตั้งชื่อใบงานเอง — หยุดตั้งชื่ออัตโนมัติจากค่าที่กรอกสำหรับใบนี้"""
    data = request.get_json(force=True, silent=True) or {}
    title = str(data.get("title") or "").strip()
    if not title:
        return jsonify({"error": t("api.sheetNeedTitle")}), 400
    try:
        path = _sheet_file(current_user(), name)
        body = save_sheet(path, {"title": title, "rename": True})
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except FormDataError as e:
        return jsonify({"error": str(e)}), 400
    log.info("sheet renamed name=%s", path.name)
    return jsonify(_sheet_response(path, body))


@app.post("/api/sheets/<name>/relink")
@login_required
def sheets_relink(name):
    """ย้ายใบนี้ไปใช้ฟอร์มต้นฉบับเวอร์ชันปัจจุบัน — ผู้ใช้สั่งเองเท่านั้น

    หมุดยังอยู่พิกัดเดิม ถ้าฟอร์มใหม่วางช่องคนละที่ ผู้ใช้ต้องเลื่อนหมุดเอง
    ดีกว่าเปลี่ยนให้เงียบ ๆ แล้วพิมพ์ออกมาผิดช่องโดยไม่รู้ตัว
    """
    user = current_user()
    try:
        path = _sheet_file(user, name)
        data = sheet_core.read_sheet(path)
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except FormDataError as e:
        return jsonify({"error": str(e)}), 400

    source_doc = str(data.get("source_doc") or "")
    if not source_doc:
        return jsonify({"error": t("api.sheetNeedSource")}), 400
    try:
        sha, _lic = _snapshot_for_source(user, source_doc)
    except PermissionError as e:
        return _license_required_response(str(e))
    except (ValueError, FileNotFoundError) as e:
        return jsonify({"error": str(e)}), 404

    old_sha = data["form_sha"]
    if sha == old_sha:
        return jsonify(_sheet_response(path, data))
    body = save_sheet(path, {"form_sha": sha})
    freed = form_store.collect_garbage(
        user_paths(user)["forms"], sheet_core.referenced_shas(user_paths(user)["sheets"])
    )
    log.info("sheet relinked name=%s %s -> %s freed=%s",
             path.name, old_sha[:12], sha[:12], len(freed))
    return jsonify(_sheet_response(path, body))


@app.get("/api/sheets/<name>/export")
@login_required
def sheets_export(name):
    """ส่งออกเป็น .fromdd — ไฟล์เดียวจบในตัว ส่งให้เครื่องที่ไม่มีฟอร์มได้"""
    paths = user_paths(current_user())
    try:
        path = _sheet_file(current_user(), name)
        data = sheet_core.read_sheet(path)
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except FormDataError as e:
        return jsonify({"error": str(e)}), 400
    tmp_dir = _sheet_export_dir(paths)
    # ชื่อไฟล์ที่ผู้ใช้จะเห็นตอนโหลด — เอาชื่อใบงาน ไม่ใช่ชื่อไฟล์ภายในที่มีแต่ตัวเลขเวลา
    dest = tmp_dir / job_core.job_filename(
        title_to_filename(str(data.get("title") or ""), path.stem)
    )
    try:
        fromdd_io.export_fromdd(dest, paths["forms"], data)
    except (FormDataError, FileNotFoundError, OSError) as e:
        log.warning("sheet export failed name=%s err=%s", path.name, e)
        return jsonify({"error": t("api.sheetExportFail")}), 400
    return send_file(dest, as_attachment=True, download_name=dest.name)


@app.post("/api/sheets/import")
@login_required
def sheets_import():
    """นำเข้า .fromdd จากเครื่องอื่น — แตกเป็นใบงาน + สแนปช็อตฟอร์ม"""
    paths = user_paths(current_user())
    f = request.files.get("file")
    if f is None or not (f.filename or "").lower().endswith(job_core.JOB_EXT):
        return jsonify({"error": t("api.sheetImportNeedsFile")}), 400
    staged = _sheet_export_dir(paths) / ("import-" + job_core.job_filename(Path(f.filename).stem))
    try:
        f.save(staged)
        body = fromdd_io.import_fromdd(
            paths["sheets"], paths["forms"], staged, base_name=Path(f.filename).stem
        )
    except FormDataError as e:
        return jsonify({"error": str(e)}), 400
    except OSError as e:
        log.warning("sheet import failed err=%s", e)
        return jsonify({"error": t("api.sheetImportFail")}), 400
    finally:
        try:
            staged.unlink(missing_ok=True)
        except OSError:
            pass
    path = paths["sheets"] / body["name"]
    log.info("sheet imported name=%s", body["name"])
    return jsonify(_sheet_response(path, body))


@app.post("/api/fill")
@login_required
def fill():
    data = request.get_json(force=True, silent=True) or {}
    doc_name = data.get("doc") or ""
    fields = data.get("fields") or []
    font = thai_font()
    if not font:
        log.error("fill aborted: Thai font missing")
        return jsonify({"error": t("api.thaiFontMissing")}), 500

    if is_out_doc(doc_name):
        return jsonify({"error": t("api.fillFromHistory")}), 400
    try:
        src, lic_doc = _resolve_open_pdf(current_user(), doc_name)
    except (ValueError, FileNotFoundError, FormDataError) as e:
        return jsonify({"error": str(e)}), 404
    if not src.exists():
        return jsonify({"error": t("api.pdfMissing")}), 404
    ok, lic_err = can_fill_document(DATA_DIR, lic_doc, src)
    if not ok:
        log.warning("fill blocked by license doc=%s", src.name)
        return jsonify({"error": lic_err, "license_required": True}), 402

    paths = user_paths(current_user())
    sheet_name = str(data.get("sheet") or "").strip()
    sheet_path: Optional[Path] = None
    out_base = data.get("outname") or src.stem
    if sheet_name:
        try:
            sheet_path = _sheet_file(current_user(), sheet_name)
            out_base = data.get("outname") or sheet_core.read_sheet(sheet_path).get("title") or src.stem
        except (FormDataError, FileNotFoundError, ValueError):
            sheet_path = None
    out_path: Optional[Path] = None
    out_name = ""

    try:
        out_name = unique_output_name(paths["output"], out_base)
        out_path = paths["output"] / out_name
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
        if out_path is not None:
            try:
                out_path.unlink(missing_ok=True)
            except OSError:
                pass
        eid = getattr(g, "event_id", new_event_id())
        log.exception("fill failed event=%s doc=%s", eid, safe_name(doc_name))
        return jsonify({
            "error": t("api.fillFail", eid=eid),
            "event_id": eid,
        }), 500

    if sheet_path is not None:
        sheet_core.note_printed(sheet_path, out_name)

    archived = None
    if is_lib_doc(doc_name):
        try:
            archived = archive_filled_beside(src, out_path)
        except OSError:
            log.exception("archive filled copy failed")
    log.info("fill ok fields=%s out=%s archived=%s", used, out_name, archived or "-")
    return jsonify({"ok": True, "file": out_name, "archived": archived})


@app.get("/download/<name>")
@login_required
def download(name):
    path = user_paths(current_user())["output"] / (
        safe_name(name[:-4] if name.lower().endswith(".pdf") else name) + ".pdf"
    )
    if not path.exists():
        return jsonify({"error": "not found"}), 404
    return send_file(path, as_attachment=False, download_name=path.name)


@app.get("/api/history")
@login_required
def history_list():
    q = request.args.get("q") or ""
    paths = user_paths(current_user())
    pdfs = list_history(paths["output"], q)
    sheets = list_sheets(paths["sheets"], q)
    user = current_user()
    live: dict[str, Optional[str]] = {}
    for row in sheets:
        src = str(row.get("source_doc") or "")
        if src not in live:
            live[src] = _live_source_sha(user, src)
        row["source_name"] = _source_label(src)
        row["source_present"] = live[src] is not None
        row["source_changed"] = bool(live[src] and live[src] != row.get("form_sha"))
    files = list(sheets) + list(pdfs.get("files") or [])
    files.sort(key=lambda d: (-int(d.get("mtime") or 0), str(d.get("name") or "")))
    truncated = bool(pdfs.get("truncated")) or len(files) > HISTORY_LIMIT
    files = files[:HISTORY_LIMIT]
    return jsonify({
        "count": len(files),
        "truncated": truncated,
        "files": files,
        "open_folder_enabled": _open_folder_allowed(),
    })


@app.post("/api/history/open")
@machine_admin_required
def history_open():
    if not _open_folder_allowed():
        return jsonify({"error": t("api.openFolderLocalOnly")}), 403
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "").strip()
    kind = (data.get("kind") or "").strip().lower()
    paths = user_paths(current_user())
    sheets_dir = paths["sheets"]
    output = paths["output"]
    if not name:
        target = sheets_dir
    elif kind == "sheet" or name.lower().endswith(".json"):
        try:
            fname = sheet_filename(name)
        except FormDataError as e:
            return jsonify({"error": str(e)}), 400
        target = sheets_dir / fname
        if not target.is_file():
            return jsonify({"error": t("api.sheetMissing")}), 404
    else:
        try:
            fname = out_filename_from_doc(name) if is_out_doc(name) else (
                safe_name(name[:-4] if name.lower().endswith(".pdf") else name) + ".pdf"
            )
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        target = output / fname
        if not target.is_file():
            return jsonify({"error": t("api.historyMissing")}), 404
    try:
        if target.is_file() and sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", str(target)])
        else:
            _open_in_explorer(target if target.is_dir() else target.parent)
    except OSError:
        log.exception("history open failed")
        return jsonify({"error": t("api.openExplorerFail")}), 500
    return jsonify({"ok": True, "path": str(target)})


@app.post("/api/open-folder")
@machine_admin_required
def open_folder():
    if not _open_folder_allowed():
        return jsonify({
            "error": t("api.openFolderLocalOnly"),
        }), 403
    data = request.get_json(force=True, silent=True) or {}
    which = (data.get("which") or "").strip().lower()
    user = current_user()
    paths = user_paths(user)
    mapping = {
        "data": DATA_DIR,
        "output": paths["output"],
        "sheets": paths["sheets"],
        "work": paths["work"],
        "logs": LOG_DIR,
        "uploads": paths["uploads"],
    }
    target = mapping.get(which)
    if target is None:
        return jsonify({"error": t("api.badWhich")}), 400
    try:
        _open_in_explorer(target)
    except OSError:
        log.exception("open-folder failed which=%s", which)
        return jsonify({"error": t("api.openFolderFail")}), 500
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
@machine_admin_required
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
        return jsonify({"error": t("api.reportFail")}), 500

    buf.seek(0)
    log.info("support-report created %s", download_name)
    return send_file(
        buf,
        mimetype="application/zip",
        as_attachment=True,
        download_name=download_name,
    )


@app.post("/api/backup")
@machine_admin_required
def api_backup():
    """สำรอง uploads + templates + output + library settings — ไม่มี machine_id/license"""
    user = current_user()
    paths = user_paths(user)
    try:
        buf, filename, meta = create_backup_zip(
            data_dir=DATA_DIR,
            username=user or LOCAL_USER,
            user_root=paths["root"],
            work_root=paths["work"],
            app_version=APP_VERSION,
        )
    except OSError:
        log.exception("backup failed")
        return jsonify({"error": t("api.backupFail")}), 500
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
@machine_admin_required
def api_restore():
    """กู้จาก ZIP — mode=merge|replace; ไม่เขียน machine_id/license"""
    mode = (request.form.get("mode") or request.args.get("mode") or "merge").strip().lower()
    if mode not in ("merge", "replace"):
        return jsonify({"error": t("api.badRestoreMode")}), 400
    if "file" not in request.files:
        return jsonify({"error": t("api.noZip")}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": t("api.noFilename")}), 400
    raw = io.BytesIO(f.read())
    user = current_user()
    paths = user_paths(user)
    try:
        result = restore_backup(
            raw,
            user_root=paths["root"],
            work_root=paths["work"],
            data_dir=DATA_DIR,
            mode=mode,  # type: ignore[arg-type]
        )
    except (ValueError, zipfile.BadZipFile) as e:
        return jsonify({"error": str(e)}), 400
    except OSError:
        log.exception("restore failed")
        return jsonify({"error": t("api.restoreFail")}), 500
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
        return jsonify({"error": t("api.tplMissing")}), 404
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
        return jsonify({"error": t("api.noFile")}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": t("api.noFilename")}), 400
    raw_name = f.filename
    stem = os.path.splitext(raw_name)[0]
    if stem.lower().endswith(".tpl"):
        stem = stem[:-4]
    name = safe_name(stem)
    if not name:
        return jsonify({"error": t("api.badTplName")}), 400
    try:
        payload = json.loads(f.read().decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return jsonify({"error": t("api.needJson")}), 400
    if not isinstance(payload, dict):
        return jsonify({"error": t("api.badTplFormat")}), 400
    overwrite = (request.form.get("overwrite") or "").lower() in ("1", "true", "yes")
    path = user_paths(current_user())["templates"] / (name + ".json")
    if path.exists() and not overwrite:
        return jsonify({"error": t("api.tplExists", name=name), "name": name}), 409
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log.info("template imported name=%s", name)
    return jsonify({"ok": True, "name": name})


@app.get("/api/formpack")
@login_required
def api_formpack_list():
    pack = BASE / "formpacks" / "v1"
    return jsonify({
        "id": "v1",
        "title": "School form pack v1" if get_locale() == "en" else "แพ็กฟอร์มโรงเรียน v1",
        "templates": list_formpack_templates(pack),
        "note_th": (
            "Sample field positions — match them to your school's real PDF after install"
            if get_locale() == "en"
            else "เทมเพลตตัวอย่างตำแหน่งฟิลด์ — ต้องจับคู่กับ PDF จริงของโรงเรียนหลังติดตั้ง"
        ),
        "note": (
            "Sample field positions — match them to your school's real PDF after install"
            if get_locale() == "en"
            else "เทมเพลตตัวอย่างตำแหน่งฟิลด์ — ต้องจับคู่กับ PDF จริงของโรงเรียนหลังติดตั้ง"
        ),
    })


@app.post("/api/formpack/install")
@login_required
def api_formpack_install():
    if not _paid_license():
        return _license_required_response(t("api.formpackNeedsLicense"))
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
        return jsonify({"error": t("api.formpackFail")}), 500
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
            "error": t("api.internalError", eid=eid),
            "event_id": eid,
        }), 500
    return (
        (
            f"<h1>{html.escape(t('api.errorPageTitle'))}</h1>"
            f"<p>{html.escape(t('api.eventId'))} <code>{html.escape(eid)}</code></p>"
            f"<p>{html.escape(t('api.errorPageBody'))}</p>"
        ),
        500,
    )


def create_app():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    USERS_DIR.mkdir(parents=True, exist_ok=True)
    # windowed frozen: sys.stderr เป็น None — ห้ามติด StreamHandler
    init_logging(LOG_DIR, console=not is_frozen())
    app.secret_key = _ensure_secret_key()
    if (
        AUTH_REQUIRED
        and _bind_host() not in ("127.0.0.1", "localhost", "::1")
        and os.environ.get("ADMIN_PASSWORD", "changeme") == "changeme"
        and not os.environ.get("USERS_JSON", "").strip()
    ):
        raise RuntimeError(
            "Refusing network startup with the default admin password; "
            "set ADMIN_PASSWORD or USERS_JSON"
        )
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
