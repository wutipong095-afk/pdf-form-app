# ROADMAP — PDF Form Marker (School-first)

เอกสารวางแผนพัฒนาสำหรับตลาดโรงเรียนไทย  
อัปเดตล่าสุด: 2026-07-18

## เป้าหมายผลิตภัณฑ์

โปรแกรม Windows ติดตั้งง่าย ใช้ออฟไลน์ได้  
ข้อมูล PDF / เทมเพลตอยู่เครื่องโรงเรียนเท่านั้น  
ขายแบบไลเซนต์ผูกเครื่อง (Ed25519) ไม่เก็บไฟล์ลูกค้าบนเซิร์ฟเวอร์ผู้ขาย

ประสบการณ์เป้าหมายรุ่นแรก:

```text
ติดตั้ง → เปิดจากไอคอน → ใส่คีย์ → เลือกฟอร์ม → กรอก → ได้ PDF → สำรองข้อมูล
```

โดยไม่ต้องเห็น Terminal, Python, Docker หรือไฟล์ config

---

## สถาปัตยกรรมเป้าหมาย (ย่อ)

```text
ไอคอน Desktop
    → โปรแกรม Python (Flask/Waitress @ 127.0.0.1)
        → UI TypeScript (Vite build → static/)
        → PyMuPDF + ฟอนต์สารบรรณ
        → ไลเซนต์ในเครื่อง
        → คลังเอกสารที่ผู้ใช้เลือกโฟลเดอร์เอง
```

| ส่วน | ทิศทาง |
|------|--------|
| Backend | **Python** — Flask + PyMuPDF (เครื่องยนต์ PDF ไทย) |
| Frontend | **TypeScript** — Vite แยกโฟลเดอร์ `frontend/` แล้ว build เข้า `static/` |
| Runtime | Windows desktop, bind `127.0.0.1` |
| ข้อมูลระบบ | `%LOCALAPPDATA%\PDFFormMarker\` (license, machine_id, logs) |
| คลังเอกสาร | ผู้ใช้กำหนดโฟลเดอร์รากเอง + โฟลเดอร์ย่อยตามงาน |
| Auth | ค่าเริ่มต้นไม่บังคับ login; PIN เป็นทางเลือก |
| Docker/Caddy | เก็บเป็นโหมดนักพัฒนา / ขั้นสูง ไม่ใช่คู่มือโรงเรียน |

### ทำไมเป็น Hybrid (Python + TypeScript)

| ชั้น | ภาษา | เหตุผล |
|------|------|--------|
| PDF / license / ไฟล์ | Python | PyMuPDF + โค้ด license ที่มีอยู่แล้ว แข็งแรงและทดสอบแล้ว |
| UI / ค้นหา / คลังเอกสาร | TypeScript | โครงใหญ่ขึ้นจะดูแลง่าย มี type กันบั๊ก ขยายหน้าจอโรงเรียนได้ |

**ไม่**ย้าย backend ทั้งก้อนไป Node ในระยะใกล้ — ไลบรารี PDF ไทยและ license ปัจจุบันผูกกับ Python

รายละเอียด deploy ปัจจุบัน: [DEPLOY.md](DEPLOY.md)  
คู่มือรันพัฒนา: [README.md](README.md)  
Frontend: โฟลเดอร์ [`frontend/`](frontend/)

---

## เช็กพอยต์หลัก (Checkpoints)

ใช้เป็นเกณฑ์ผ่านก่อนเริ่มระยะถัดไป

| ID | ชื่อ | ผ่านเมื่อ |
|----|------|-----------|
| CP0 | พื้นฐานพร้อมพัฒนา | มี license Ed25519, Thai PDF fill, demo ใช้งานได้บน local |
| CP-TS | Frontend TypeScript | มี `frontend/` (Vite+TS), build เข้า `static/`, UI หลักไม่พึ่ง JS ใน `<script>` ก้อนเดียว |
| CP1 | School baseline | โหมดเครื่องเดียวไม่บังคับ login, DATA_DIR ชัด, bind localhost, มี logging พื้นฐาน |
| CP2 | คลังเอกสาร v1 | เลือกโฟลเดอร์รากได้, สแกน/ค้นจากชื่อ+โฟลเดอร์, เปิดใน Explorer ได้ |
| CP3 | Backup / Restore | สำรองและกู้เป็น ZIP ได้โดยไม่พัง license ของเครื่องใหม่ |
| CP4 | Windows installer | ติดตั้งจาก Setup.exe เปิดจากไอคอนได้โดยไม่ต้องรู้ Python | ✅ |
| CP5 | Form pack โรงเรียน | มีแพ็กฟอร์มพร้อมมาร์คอย่างน้อย 3–5 แบบที่ใช้บ่อย |
| CP6 | Pilot โรงเรียน | ทดลองกับโรงเรียนจริง ≥ 2 แห่ง ครบ 1 สัปดาห์ใช้งานจริง |
| CP7 | Ready to sell | คู่มือไทย, ช่องทางออกคีย์, วิดีโอสั้น, นโยบายซัพพอร์ต 5 ปี ชัดเจน |

สถานะปัจจุบันโดยประมาณ: **CP0–CP4** · ต่อไป **CP5–CP7** (pilot + พร้อมขาย; วิดีโอคู่มือยังเป็น follow-up)

---

## ระยะพัฒนา

### ระยะ 0 — สถานะปัจจุบัน (เสร็จแล้วบางส่วน)

- [x] กรอก PDF ทับด้วยข้อความไทย (PyMuPDF + Thai shaping)
- [x] มาร์คจุด / บันทึกเทมเพลต JSON
- [x] ไลเซนต์ผูกเครื่อง Ed25519 (`license_core.py`)
- [x] Demo form + seed ต่อผู้ใช้
- [x] Docker deploy (โหมดขั้นสูง)
- [x] Scaffold `frontend/` (Vite + TypeScript)
- [x] ย้าย UI หลักจาก `templates/index.html` inline JS → TypeScript modules
- [x] โหมดโรงเรียนเป็นค่าเริ่มต้นในเอกสารหลัก

**ทางออก:** CP0

---

### ระยะ 0.5 — Frontend TypeScript

เป้าหมาย: พัฒนาหน้าจอด้วย TypeScript แบบมี type และแยกโมดูล

โครงสร้าง:

```text
frontend/
  src/
    app.ts / api.ts / types.ts / state.ts
    license.ts / docs.ts / viewer.ts / fields.ts / chat.ts
  vite.config.ts    # build → ../static/js/app.js
```

งาน:

- [x] สร้างโปรเจกต์ Vite + TypeScript ใน `frontend/`
- [x] `npm run build` แล้ว Flask เสิร์ฟจาก `static/`
- [x] ย้าย license / docs / มาร์คจุด / กรอก / สร้าง PDF ไป TS
- [x] ลบ inline `<script>` ก้อนใหญ่ใน `templates/index.html`
- [x] Dev: `vite` proxy ไป Flask (`localhost:5000`)
- [x] Client error → `POST /api/client-log` (ทำคู่ logging ระยะ 1)

**ทางออก:** CP-TS

---

### ระยะ 1 — School baseline + Logging

เป้าหมาย: ใช้ในโรงเรียน 1 เครื่องได้อย่างปลอดภัยและตรวจปัญหาได้

#### งานผลิตภัณฑ์

- [x] ค่าเริ่มต้น `HOST=127.0.0.1`
- [x] `DATA_DIR` ชี้ `%LOCALAPPDATA%\PDFFormMarker\data` บน Windows
- [x] โหมดเครื่องเดียว: เข้าใช้งานได้โดยไม่บังคับ login (เก็บ login เป็น Advanced)
- [x] ปุ่มเปิดโฟลเดอร์ข้อมูล / โฟลเดอร์ผลลัพธ์
- [x] แยก README เป็น “โรงเรียน” vs “นักพัฒนา”
- [x] ปิด `LICENSE_BYPASS` ใน build ปล่อยจริง (ค่าเริ่มต้นปิด; Docker ไม่เปิด; เตือนใน log ถ้าเปิด)

#### งาน Logging / ตรวจจับ Error (เริ่มที่ระยะนี้)

ดูรายละเอียดในหัวข้อ [แผน Logging และตรวจจับ Error](#แผน-logging-และตรวจจับ-error)

- [x] โมดูล `logging_setup.py` มาตรฐานทั้งแอป
- [x] เขียน log ลงไฟล์หมุนเวียน (rotating)
- [x] จับ exception ที่ยังไม่ถูกจัดการ (Flask + thread หลัก)
- [x] หน้า/ปุ่ม “ส่งรายงานปัญหา” = แพ็ก log ล่าสุดเป็น ZIP (ไม่มี PDF เนื้อหา)

**ทางออก:** CP1

---

### ระยะ 2 — คลังเอกสารที่ผู้ใช้กำหนดเอง

เป้าหมาย: หาฟอร์มง่าย จัดโฟลเดอร์ตามงานโรงเรียนได้

#### โครงสร้างแนะนำ

```text
<โฟลเดอร์รากที่ผู้ใช้เลือก>\
├── 01-การเงิน\
├── 02-พัสดุ\
├── 03-บุคคล\
└── .pdfmarker\
    ├── index.json      # ดัชนีค้นหา
    └── settings.json   # ค่าตั้งค่าคลัง
```

ข้อมูลระบบ (license / machine_id / logs) อยู่ AppData แยกต่างหาก

#### งาน

- [x] Settings: เลือกโฟลเดอร์รากเอกสาร (`DATA_DIR/library.json` + UI)
- [x] สร้างโครงเริ่มต้น / สแกนคลัง (`01-การเงิน` ฯลฯ + `.pdfmarker/`)
- [x] รองรับโฟลเดอร์ย่อยไม่จำกัดความลึก (หรือจำกัดระดับที่สมเหตุสมผล เช่น 3)
- [x] ดัชนี `.pdfmarker/index.json` (ชื่อ, path, โฟลเดอร์, แท็ก, ใช้ล่าสุด)
- [x] ช่องค้นหาเดียว: ชื่อ / โฟลเดอร์ / แท็ก / ล่าสุด
- [x] ปุ่มเปิดใน Explorer (ราก + เลือกไฟล์)
- [x] จับคู่เทมเพลต: `ชื่อ.pdf` + `ชื่อ.tpl.json` (รุ่นแรก) หรือผูกผ่าน metadata
- [x] ปุ่มสแกนใหม่ / โหลดดัชนีตอนเปิด (เก็บ mtime/size + คง tags/last_used; walk ครบโฟลเดอร์เมื่อสแกน)

**ทางออก:** CP2

---

### ระยะ 3 — Backup / Restore + Form packs

- [x] สำรอง ZIP: originals + templates + filled + settings คลัง
- [x] กู้คืนแบบ merge / แทนที่ (ถามผู้ใช้)
- [x] ไม่บังคับย้าย `machine_id` ไปเครื่องใหม่ (ต้องออกคีย์ใหม่)
- [x] Export / Import เทมเพลตเดี่ยว
- [x] Form pack v1: อย่างน้อย ใบเบิก / จัดซื้อ / เดินทาง (หรือฟอร์มที่โรงเรียนเป้าใช้จริง)
- [x] คู่มือสั้น ([docs/BACKUP.md](docs/BACKUP.md)) — วิดีโอ 3–5 นาทีเป็น follow-up

**ทางออก:** CP3 (+ Form pack v1); วิดีโอยังค้าง

---

### ระยะ 4 — Windows installer

- [x] แพ็กด้วย PyInstaller (one-folder) — `PDFFormMarker.spec` + `launcher.py`
- [x] Inno Setup → Start Menu + Desktop shortcut — `installer/PDFFormMarker.iss`
- [x] Bundle ฟอนต์สารบรรณ + demo + formpacks + `license_public.pem`
- [x] First-run: สร้าง DATA_DIR, SECRET_KEY, เปิดเบราว์เซอร์ + หน้าต่างสถานะ
- [x] ไม่ใส่ `scripts/gen_license.py` / private key ในตัวติดตั้งลูกค้า
- คู่มือแพ็ก: [docs/INSTALLER.md](docs/INSTALLER.md) · สคริปต์: `scripts/build_windows.ps1`

**ทางออก:** CP4

---

### ระยะ 5 — นำร่องและพร้อมขาย

- [ ] ทดลองโรงเรียนจริง ≥ 2 แห่ง
- [ ] เก็บปัญหาจาก log + สัมภาษณ์ผู้ใช้
- [ ] ปรับ UX ตาม feedback (ค้นหา, สำรอง, เปิดฟอร์ม)
- [ ] ช่องทางออกคีย์ (แชต/อีเมล) + ใบเสร็จ
- [ ] นโยบายดูแล 5 ปี / ย้ายเครื่อง ปีละกี่ครั้ง
- [ ] เวอร์ชันโปรแกรม + แจ้งมีอัปเดต (ไม่บังคับออนไลน์ตอนใช้งาน)

**ทางออก:** CP6 + CP7

---

## แผน Logging และตรวจจับ Error

เป้าหมาย: เมื่อโรงเรียนใช้งานพัง ผู้ขายขอ “ไฟล์รายงานปัญหา” ได้ โดย**ไม่ได้รับ PDF/ข้อมูลส่วนบุคคล**

### หลักการ

| หลัก | รายละเอียด |
|------|------------|
| Log อยู่ในเครื่องลูกค้า | `%LOCALAPPDATA%\PDFFormMarker\logs\` |
| ไม่ log เนื้อหาฟอร์ม | ห้ามเขียนค่าที่กรอก / path เต็มที่อาจมีชื่อคน ถ้าไม่จำเป็น |
| หมุนไฟล์อัตโนมัติ | กันดิสก์เต็ม |
| แยกระดับ | INFO ใช้งานปกติ, WARNING ผิดปกติแต่ไปต่อได้, ERROR พังแล้ว |
| Privacy by default | ปุ่มส่งรายงานต้องให้ผู้ใช้กดเอง |

### โครงสร้างไฟล์ Log

```text
%LOCALAPPDATA%\PDFFormMarker\logs\
├── app.log              # ปัจจุบัน
├── app.log.1            # หมุนเวียน
├── errors.log           # ERROR+ เท่านั้น (อ่านเร็วตอนซัพพอร์ต)
└── reports\
    └── report-2026-07-18-103012.zip
```

ค่าเริ่มต้นแนะนำ:

- Rotating: ขนาดไฟล์ละ ~1–2 MB, เก็บ 5 ไฟล์
- Encoding: UTF-8
- รูปแบบบรรทัด: `เวลา | ระดับ | โมดูล | ข้อความ`

ตัวอย่าง:

```text
2026-07-18 10:31:02 | INFO  | fill | สร้าง PDF สำเร็จ fields=12 out=filled-xxx.pdf
2026-07-18 10:32:11 | ERROR | license | เปิดใช้ไลเซนต์ไม่สำเร็จ reason=clock_rollback
2026-07-18 10:33:00 | ERROR | app | Unhandled exception path=/api/fill
```

### สิ่งที่ต้อง log

| เหตุการณ์ | ระดับ | หมายเหตุ |
|-----------|-------|----------|
| เปิดแอป / เวอร์ชัน / OS | INFO | ช่วยซัพพอร์ต |
| สถานะไลเซนต์ (มี/หมดอายุ/demo) | INFO | ไม่ต้อง log คีย์เต็ม |
| อัปโหลด PDF สำเร็จ/ล้มเหลว | INFO/ERROR | บันทึกชื่อไฟล์ที่ sanitize แล้ว |
| บันทึกเทมเพลต | INFO | ชื่อเทมเพลต + จำนวนจุด |
| สร้าง PDF สำเร็จ | INFO | จำนวนฟิลด์ที่ใช้, ชื่อไฟล์ออก |
| สร้าง PDF ล้มเหลว | ERROR | exception type + message สั้น |
| สแกนคลังเอกสาร | INFO | จำนวนไฟล์ที่เจอ |
| Backup / Restore | INFO/ERROR | สำเร็จหรือเหตุผลล้มเหลว |
| Exception ที่ไม่คาดคิด | ERROR | stack trace ใน errors.log |

### สิ่งที่ห้าม log

- ข้อความที่ผู้ใช้กรอกลงฟอร์ม
- เนื้อหาหน้า PDF / ภาพ preview
- License key ทั้งก้อน (โชว์ท้าย 4 ตัวพอถ้าจำเป็น)
- รหัสผ่าน / SECRET_KEY
- Path ที่อาจมีชื่อบุคคล ถ้าเลี่ยงได้ให้ใช้ relative path ในคลัง

### จุดติดตั้งในโค้ด (แผน implement)

| จุด | การทำ |
|-----|--------|
| สตาร์ทแอป | `logging_setup.init_logging(log_dir)` |
| Flask | `@app.errorhandler(Exception)` + `got_request_exception` |
| `/api/fill`, upload, template, license | try/except ที่มีอยู่แล้ว → `logger.exception(...)` |
| UI (เบราว์เซอร์) | `window.onerror` / `unhandledrejection` → `POST /api/client-log` (อัตราจำกัด) |
| ปุ่มรายงานปัญหา | แพ็ก `app.log*` + `errors.log` + เวอร์ชัน + สถานะไลเซนต์ (ไม่มี uploads/output) |

### ระดับตรวจจับ Error (Detection)

1. **Local detection (ทำก่อน)**  
   - Unhandled exception → เขียน `errors.log`  
   - UI แสดงข้อความสั้น + “คัดลอกรหัสเหตุการณ์” (เช่น `E-20260718-1033`)

2. **Support pack (ทำคู่ระยะ 1–2)**  
   - ผู้ใช้กด “สร้างไฟล์รายงานปัญหา”  
   - ได้ ZIP ส่งไลน์/อีเมลผู้ขายเอง

3. **Optional ภายหลัง (ไม่บังคับโรงเรียนออนไลน์)**  
   - ถ้าผู้ใช้ยอม: ส่งเฉพาะ metadata 匿名 (เวอร์ชัน, OS, รหัส error)  
   - **ห้าม**เป็นค่าเริ่มต้น และห้ามอัปโหลด PDF

### เช็กพอยต์ Logging

| ID | ผ่านเมื่อ |
|----|-----------|
| L1 | มีไฟล์ `app.log` หลังรันแอป และหมุนเวียนได้ | ✅ |
| L2 | ทำให้ `/api/fill` พังโดยจงใจแล้วเห็น stack ใน `errors.log` | ✅ (handler + `log.exception` ใน fill) |
| L3 | ปุ่มสร้าง report ZIP ได้ และใน ZIP ไม่มีไฟล์จาก `uploads/` / `output/` | ✅ |
| L4 | UI error ส่งเข้า client-log ได้โดยไม่สแปม (rate limit) | ✅ |

---

## ลำดับงานที่แนะนำให้ทำจริง (สั้น)

1. Frontend TypeScript scaffold + ย้าย API/license ไป TS (**CP-TS** เริ่ม)  
2. Logging พื้นฐาน + error handler (**L1–L2**)  
3. School baseline: localhost + AppData + โหมดไม่ login (**CP1**)  
4. ย้าย UI กรอกฟอร์มครบไป TypeScript (**CP-TS** เสร็จ)  
5. คลังเอกสารเลือกโฟลเดอร์ได้ + ค้นหา (**CP2**)  
6. Backup ZIP + report ZIP (**CP3 + L3**)  
7. Installer (**CP4**) — ✅ PyInstaller + Inno Setup (`scripts/build_windows.ps1`)  
8. Pilot + พร้อมขาย (**CP5–CP7**)

---

## นอกขอบเขตระยะใกล้

- SaaS บังคับอัปโหลด PDF ขึ้นคลาวด์ผู้ขาย  
- คิดเงินรายครั้งสร้าง PDF  
- OCR ค้นข้อความในลายสแกนทั้งเครื่อง  
- Multi-tenant ซับซ้อนสำหรับโรงเรียนขนาดเล็ก  

---

## การตัดสินใจที่ล็อกแล้ว (จากบทสนทนาก่อนหน้า)

| หัวข้อ | คำตัดสิน |
|--------|----------|
| ตลาดแรก | โรงเรียน / หน่วยงานราชการ |
| โมเดลขาย | ขายขาด ~500 บาท ดูแล 5 ปี / เครื่อง |
| ที่รัน | เครื่องผู้ใช้ (local-first) |
| ไลเซนต์ | Ed25519 ผูกเครื่อง |
| ภาษา | Backend Python + Frontend TypeScript (ไม่ย้าย PDF engine ไป Node) |
| Docker | ไม่ใช่เส้นทางหลักของโรงเรียน |

---

## ประวัติเอกสาร

| วันที่ | หมายเหตุ |
|--------|----------|
| 2026-07-18 | ร่างแรก: โรดแมปโรงเรียน + เช็กพอยต์ + แผน logging/ตรวจจับ error |
| 2026-07-18 | เพิ่ม Hybrid Python + TypeScript, เช็กพอยต์ CP-TS, scaffold `frontend/` |
| 2026-07-18 | CP1 + logging L1–L4: AppData DATA_DIR, ไม่บังคับ login, client-log, support-report ZIP |
| 2026-07-19 | แก้ตามรีวิว: fallback `./data` เดิม, จำกัด open-folder นอก localhost, ignore `.pdfmarker/` |
| 2026-07-19 | แก้ findings PR: secret_key O_EXCL, legacy marker, LOG_PER_WORKER, TRUST_XFF, BytesIO report |
| 2026-07-19 | CP2 คลังเอกสาร: เลือกโฟลเดอร์ราก, สแกน/ค้นหา, `@lib.` + `ชื่อ.tpl.json`, เปิด Explorer |
| 2026-07-19 | แก้รีวิว CP2: atomic index, base64url doc id, escape UI, save-tpl คลัง |
| 2026-07-20 | CP3 Backup/Restore + Form pack v1 + docs/BACKUP.md (วิดีโอยังค้าง) |
| 2026-07-20 | CP4 Windows installer: PyInstaller + Inno Setup + docs/INSTALLER.md |
