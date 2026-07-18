# PDF Form Marker — มาร์คจุดบน PDF แล้วเติมข้อมูลเป็นเลเยอร์ทับ
# รัน local: python app.py  →  http://localhost:5000
from __future__ import annotations

import html
import io
import json
import os
import re
import shutil
import time
from functools import wraps
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF
from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from envutil import BASE, load_dotenv
from license_core import (
    DEMO_DOC_NAME,
    activate_license,
    can_fill_document,
    file_sha256,
    license_status,
)

load_dotenv()
DEMO_DIR = BASE / "demo"
DATA_DIR = Path(os.environ.get("DATA_DIR", BASE / "data")).resolve()
USERS_DIR = DATA_DIR / "users"
FONTS_DIR = BASE / "fonts"

ZOOM = 2.0
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "16"))

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


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
if os.environ.get("SESSION_COOKIE_SECURE", "").lower() in ("1", "true", "yes"):
    app.config["SESSION_COOKIE_SECURE"] = True


def current_user() -> Optional[str]:
    return session.get("user")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            if request.path.startswith("/api/") or request.path.startswith("/page/") or request.path.startswith("/download/"):
                return jsonify({"error": "unauthorized"}), 401
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


@app.route("/login", methods=["GET", "POST"])
def login():
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
            nxt = request.args.get("next") or url_for("index")
            if not nxt.startswith("/"):
                nxt = url_for("index")
            return redirect(nxt)
        error = "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง"
    return render_template("login.html", error=error)


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.get("/")
@login_required
def index():
    return render_template("index.html", user=current_user())


@app.get("/api/me")
@login_required
def me():
    return jsonify({"user": current_user(), "license": license_status(DATA_DIR)})


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
        return jsonify({"ok": True, **st})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        # ปัญหา config ฝั่งแอป (public key หาย/ไฟล์รหัสเครื่องเสีย) ไม่ใช่คีย์ผิด
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
    f.save(paths["uploads"] / name)
    return jsonify({"ok": True, "name": name})


def _pdf_path(username: str, doc: str) -> Path:
    name = safe_name(doc[:-4] if doc.lower().endswith(".pdf") else doc) + ".pdf"
    return user_paths(username)["uploads"] / name


@app.get("/api/pageinfo/<doc>")
@login_required
def pageinfo(doc):
    path = _pdf_path(current_user(), doc)
    if not path.exists():
        return jsonify({"error": "not found"}), 404
    with fitz.open(path) as d:
        sizes = [{"w": p.rect.width, "h": p.rect.height} for p in d]
    return jsonify({"pages": len(sizes), "sizes": sizes, "zoom": ZOOM})


@app.get("/page/<doc>/<int:pno>.png")
@login_required
def page_png(doc, pno):
    path = _pdf_path(current_user(), doc)
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
    path = user_paths(current_user())["templates"] / (safe_name(name) + ".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return jsonify({"ok": True, "name": safe_name(name)})


@app.post("/api/fill")
@login_required
def fill():
    data = request.get_json(force=True, silent=True) or {}
    doc_name = data.get("doc") or ""
    fields = data.get("fields") or []
    font = thai_font()
    if not font:
        return jsonify({"error": "ไม่พบฟอนต์ไทย — ตรวจโฟลเดอร์ fonts/"}), 500

    src = _pdf_path(current_user(), doc_name)
    if not src.exists():
        return jsonify({"error": "ไม่พบ PDF"}), 404
    ok, lic_err = can_fill_document(DATA_DIR, doc_name, src)
    if not ok:
        return jsonify({"error": lic_err, "license_required": True}), 402

    out_name = safe_name(data.get("outname") or f"filled-{int(time.time())}") + ".pdf"
    out_path = user_paths(current_user())["output"] / out_name

    with fitz.open(src) as d:
        for fld in fields:
            val = str(fld.get("value") or "").strip()
            if not val:
                continue
            page = d[int(fld["page"])]
            pt = fitz.Point(float(fld["x"]), float(fld["y"]))
            size = float(fld.get("size", 14))
            try:
                insert_thai_text(page, pt, val, size, font)
            except Exception:
                # เผื่อ insert_htmlbox ใช้ไม่ได้ — ยอมให้วรรณยุกต์เพี้ยนดีกว่าเติมไม่ได้เลย
                page.insert_text(pt, val, fontsize=size, fontname="thaifont", fontfile=font, color=(0, 0, 0))
        try:
            d.subset_fonts()  # insert_htmlbox ฝังฟอนต์เต็มไฟล์ — ตัดให้เหลือเฉพาะที่ใช้
        except Exception:
            pass
        # garbage=4 รวมฟอนต์ที่ฝังซ้ำกันหลายชุดให้เหลือชุดเดียว (ไฟล์เล็กลงมาก)
        d.save(out_path, garbage=4, deflate=True)
    return jsonify({"ok": True, "file": out_name})


@app.get("/download/<name>")
@login_required
def download(name):
    path = user_paths(current_user())["output"] / (safe_name(name[:-4] if name.lower().endswith(".pdf") else name) + ".pdf")
    if not path.exists():
        return jsonify({"error": "not found"}), 404
    return send_file(path, as_attachment=False, download_name=path.name)


def create_app():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    USERS_DIR.mkdir(parents=True, exist_ok=True)
    return app


create_app()


if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "").lower() in ("1", "true", "yes")
    app.run(host=host, port=port, debug=debug)
