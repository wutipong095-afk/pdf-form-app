# PDF Form Marker

**English:** [README.en.md](README.en.md)

โปรแกรมมาร์คจุดบน PDF แล้วเติมข้อความไทยทับเป็นเลเยอร์ (PyMuPDF + Flask)  
เจาะตลาด**โรงเรียน** — ติดตั้งใช้ในเครื่อง ออฟไลน์ได้ ไลเซนต์ผูกเครื่อง

แยกจาก vault `school-reports` — เป็นเครื่องมือกรอกฟอร์มราชการทั่วไป

แผนพัฒนา: [ROADMAP.md](ROADMAP.md) · งานค้าง: [docs/BACKLOG.md](docs/BACKLOG.md)

ในแอปสลับภาษา UI ได้ที่มุมขวาบน (**ไทย / English**)

---

## โหมดโรงเรียน (ค่าเริ่มต้น)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# ตั้ง SESSION_COOKIE_SECURE=false ใน .env ตอนรัน local
python app.py
```

เปิด http://localhost:5000 — **ไม่ต้องล็อกอิน**

| สิ่งที่แอปจัดให้ | ตำแหน่ง (Windows) |
|------------------|-------------------|
| ข้อมูล / ไลเซนต์ | `%LOCALAPPDATA%\PDFFormMarker\data` |
| ใบงาน (ค่าที่กรอก) | ตั้งเองได้จากแถบสำรอง/เทมเพลต · ค่าเริ่มต้น `%LOCALAPPDATA%\PDFFormMarker\data\users\<user>\sheets` |
| สแนปช็อตฟอร์ม (PDF ต้นฉบับ เก็บชุดเดียวต่อฟอร์ม) | `%LOCALAPPDATA%\PDFFormMarker\data\users\<user>\forms` |
| Log | `%LOCALAPPDATA%\PDFFormMarker\logs` |
| Bind | `127.0.0.1` เท่านั้น |

ในแอปมีปุ่ม **ผลลัพธ์ PDF** · **รายงานปัญหา** · **สำรองข้อมูล / กู้คืน**  
(โฟลเดอร์ระบบ `%LOCALAPPDATA%\PDFFormMarker\data` ยังใช้ภายใน — ไม่เปิดให้กดจาก UI)

หลังเปิดครั้งแรกจะมี **demo-form.pdf** + เทมเพลต **demo-ใบเบิก** ให้ลองทันที

สำรอง/กู้คืน: [docs/BACKUP.md](docs/BACKUP.md) — ZIP ไม่มี `machine_id`/license (เครื่องใหม่ต้องขอคีย์ใหม่)

ตัวติดตั้ง Windows (โรงเรียน): [docs/INSTALLER.md](docs/INSTALLER.md) — `.\scripts\build_windows.ps1`  
แพ็กเกจ Linux / macOS (แยก): [docs/PACKAGING.md](docs/PACKAGING.md) — `./scripts/build_linux.sh` · `./scripts/build_macos.sh`  
แจ้งอัปเดต (latest.json): [docs/UPDATE.md](docs/UPDATE.md)

ถ้าเคยเก็บข้อมูลใน `./data` ของโปรเจกต์อยู่แล้ว แอปจะ**ใช้โฟลเดอร์นั้นต่ออัตโนมัติ**  
(ไม่ต้องตั้งอะไร — หรือจะใส่ `DATA_DIR=./data` ใน `.env` ก็ได้)

เครื่องใหม่ที่ยังไม่มี `./data` จะเก็บที่ `%LOCALAPPDATA%\PDFFormMarker\` (Windows)

---

## Frontend (TypeScript)

UI อยู่ใน [`frontend/`](frontend/) — build เข้า `static/` ให้ Flask เสิร์ฟ

```bash
cd frontend
npm install
npm run build    # → static/js/app.js
npm run dev      # พัฒนา UI ที่ :5173 (ต้องรัน python app.py คู่กัน)
```

## CI / CD

GitHub Actions รัน `pytest` + เทส/บิวด์ frontend + ตรวจ Docker ทุก PR และทุก push เข้า `master`  
ปล่อยรุ่น: ติดแท็ก `v0.3.2` (ต้องตรง `APP_VERSION`) จะแพ็ก `FormDD-Setup-*.exe` แล้วเปิด GitHub Release เป็นสำเนา — โฮสต์หลักยังเป็น `formdd.xambrain.com` ([docs/UPDATE.md](docs/UPDATE.md))

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

---

## โหมดนักพัฒนา / หลายผู้ใช้

บังคับ login:

```env
AUTH_REQUIRED=true
ADMIN_USER=admin
ADMIN_PASSWORD=changeme
SESSION_COOKIE_SECURE=false
```

Deploy ด้วย Docker + Caddy (โหมดขั้นสูง / นักพัฒนา — **ไม่ใช่**เส้นทางหลักสำหรับโรงเรียน): ดู [DEPLOY.md](DEPLOY.md)

```bash
cp .env.example .env   # ตั้ง SECRET_KEY, รหัสผ่าน, DOMAIN — ห้ามใช้รหัสผ่าน default บนเน็ต
docker compose up -d --build
```

---

## คลังเอกสาร (CP2)

ในแอปแถบ **คลังเอกสาร**: ตั้งโฟลเดอร์ราก → สร้างโครง `01-การเงิน` / `02-พัสดุ` / `03-บุคคล` อัตโนมัติ → สแกน/ค้นหา PDF → เปิดกรอก

- ดัชนี: `<ราก>/.pdfmarker/index.json`
- เทมเพลตคู่ไฟล์: `ชื่อ.pdf` + `ชื่อ.tpl.json` ในโฟลเดอร์เดียวกัน
- path รากที่เลือกเก็บใน `DATA_DIR/library.json` (ไม่ย้ายไฟล์ PDF ออกจากคลัง)
- เอกสารในคลังอ้างอิงด้วย id แบบ `@lib.` + base64url ของ path สัมพัทธ์ (ไม่ย้ายไฟล์ออกจากคลัง)

## โครงสร้าง

| path | ความหมาย |
|------|----------|
| `app.py` | API + PDF + logging |
| `library_core.py` | สแกน/ดัชนีคลังเอกสาร |
| `logging_setup.py` | ไฟล์ log หมุนเวียน |
| `templates/` | HTML (login + แอป) |
| `frontend/` | TypeScript UI (Vite) |
| `fonts/` | ฟอนต์ไทยราชการ (TH Sarabun = เลขอาราบิก; IT๙ = เลขไทย ถ้าตั้ง `FONT_PATH`) |
| `demo/` | PDF + เทมเพลตตัวอย่าง (commit ได้) |
| `data/users/<user>/` | ใช้เมื่อตั้ง `DATA_DIR=./data` (ไม่เข้า git) |

---

## ไลเซนต์ (ผูก 1 เครื่อง อายุตามคีย์ที่ออกให้)

- ตรวจด้วย **Ed25519**: แอปมีแค่ `license_public.pem` — ลูกค้าออกคีย์เองไม่ได้
- รหัสเครื่องเก็บถาวรใน `DATA_DIR/machine_id`
- ไม่มีคีย์: สร้าง PDF ได้เฉพาะ **เนื้อหา** `demo-form.pdf` ทางการ
- มีคีย์: สร้าง PDF ได้ทุกเอกสาร จนถึงวันหมดอายุ (UTC)

ออกคีย์ (เฉพาะเครื่องผู้ขายที่มี private key):

```bash
python scripts/gen_keypair.py          # ครั้งแรกเท่านั้น
python scripts/gen_license.py <รหัสเครื่อง16ตัว>
```

ห้าม commit / ห้ามใส่ Docker: `keys/ed25519_private.pem`

ตอนพัฒนา local (อย่าเปิดบนเครื่องลูกค้า):

```env
LICENSE_BYPASS=true
```
