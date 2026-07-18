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
| `fonts/` | ฟอนต์ไทยราชการ (TH Sarabun / THSarabunIT๙) |
| `demo/` | PDF + เทมเพลตตัวอย่าง (commit ได้) |
| `data/users/<user>/` | อัปโหลด / เทมเพลต / ผลลัพธ์ ต่อผู้ใช้ (ไม่เข้า git) |
| `templates_json/` | เทมเพลตเก่าจากเครื่อง local (อ้างอิงเท่านั้น) |

## บัญชีผู้ใช้

- คนละโฟลเดอร์: `data/users/<ชื่อ>/uploads|templates_json|output`
- ตั้งค่าใน `.env`: `ADMIN_USER` + `ADMIN_PASSWORD` หรือ `USERS_JSON`

## ไลเซนต์ (ขายขาด ผูก 1 เครื่อง ดูแล 5 ปี)

- ตรวจด้วย **Ed25519**: แอปมีแค่ `license_public.pem` — ลูกค้าออกคีย์เองไม่ได้
- รหัสเครื่องเก็บถาวรใน `data/machine_id` (ทน Docker rebuild)
- ไม่มีคีย์: สร้าง PDF ได้เฉพาะ **เนื้อหา** `demo-form.pdf` ทางการ (กัน rename/เขียนทับ)
- มีคีย์: สร้าง PDF ได้ทุกเอกสาร จนถึงวันหมดอายุ (UTC)

ออกคีย์ (เฉพาะเครื่องผู้ขายที่มี private key):

```bash
python scripts/gen_keypair.py          # ครั้งแรกเท่านั้น
python scripts/gen_license.py <รหัสเครื่อง16ตัว>
```

ห้าม commit / ห้ามใส่ Docker: `keys/ed25519_private.pem`

ตอนพัฒนา local:

```env
LICENSE_BYPASS=true
```
