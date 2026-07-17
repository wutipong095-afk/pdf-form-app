# PDF Form Marker

เว็บแอปมาร์คจุดบน PDF แล้วเติมข้อความไทยทับเป็นเลเยอร์ (PyMuPDF + Flask)

แยกจาก vault `school-reports` — เป็นเครื่องมือกรอกฟอร์มราชการทั่วไป ไม่ผูกกับ workflow แผน/SAR

## รันบนเครื่อง (dev)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # แล้วแก้รหัสผ่าน
set SESSION_COOKIE_SECURE=false
python app.py
```

เปิด http://localhost:5000 — ล็อกอินด้วย `ADMIN_USER` / `ADMIN_PASSWORD` จาก `.env` (default: `admin` / `changeme`)

หลังล็อกอินจะมี **demo-form.pdf** + เทมเพลต **demo-ใบเบิก** ให้ลองทันที

## Deploy ให้คนอื่นใช้

ดู [DEPLOY.md](DEPLOY.md) — Docker + Caddy (HTTPS)

```bash
cp .env.example .env   # ตั้ง SECRET_KEY, รหัสผ่าน, DOMAIN
docker compose up -d --build
```

## โครงสร้าง

| path | ความหมาย |
|------|----------|
| `app.py` | API + login + PDF |
| `templates/` | UI (login + แอป) |
| `fonts/` | ฟอนต์ไทย bundled (Noto Sans Thai) |
| `demo/` | PDF + เทมเพลตตัวอย่าง (commit ได้) |
| `data/users/<user>/` | อัปโหลด / เทมเพลต / ผลลัพธ์ ต่อผู้ใช้ (ไม่เข้า git) |
| `templates_json/` | เทมเพลตเก่าจากเครื่อง local (อ้างอิงเท่านั้น) |

## บัญชีผู้ใช้

- คนละโฟลเดอร์: `data/users/<ชื่อ>/uploads|templates_json|output`
- ตั้งค่าใน `.env`: `ADMIN_USER` + `ADMIN_PASSWORD` หรือ `USERS_JSON`
