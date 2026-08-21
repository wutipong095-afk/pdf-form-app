# Windows installer (CP4)

**English:** [INSTALLER.en.md](INSTALLER.en.md)  
แพ็กเกจ Linux / macOS: [PACKAGING.md](PACKAGING.md)

สร้างตัวติดตั้งสำหรับโรงเรียน: ติดตั้ง → ไอคอน → เปิดเบราว์เซอร์ โดยไม่ต้องรู้ Python

ตัว Setup: English เสมอ · Thai ถ้าเครื่องแพ็กมี `Languages\Thai.isl` (สคริปต์ส่ง `/DENABLE_THAI=1` อัตโนมัติ)

## สิ่งที่ได้

| ผลลัพธ์ | ความหมาย |
|---------|----------|
| `dist/PDFFormMarker/` | โฟลเดอร์รันได้จาก PyInstaller (one-folder) |
| `dist/installer/FormDD-Setup-0.3.2.exe` | ตัวติดตั้ง Inno Setup ที่ลูกค้าเห็น (ถ้ามี ISCC) |

รวมในแพ็ก: ฟอนต์สารบรรณ, demo, `formpacks/`, `license_public.pem`, UI จาก `static/`

**ไม่รวม:** `scripts/gen_license.py`, `keys/ed25519_private.pem`, `.env`

## ความต้องการเครื่องแพ็ก (ผู้ขาย)

1. Windows + Python 3.11+
2. Node.js (build frontend)
3. [Inno Setup 6](https://jrsoftware.org/isinfo.php) — สำหรับ Setup.exe (ถ้าไม่มี จะได้แค่โฟลเดอร์ `dist/PDFFormMarker/`)

## สร้างแพ็ก

จากรากโปรเจกต์ (สคริปต์สร้าง `.venv` ให้อัตโนมัติ — อย่าใช้ Python โกลบอลที่มี torch/ฯลฯ):

```powershell
.\scripts\build_windows.ps1
```

ตัวเลือก:

```powershell
.\scripts\build_windows.ps1 -SkipInno       # แค่ PyInstaller
.\scripts\build_windows.ps1 -SkipFrontend   # ใช้ static/ ที่มีอยู่แล้ว
```

ผลลัพธ์: `dist\PDFFormMarker\PDFFormMarker.exe` และ (ถ้ามี Inno) `dist\installer\FormDD-Setup-0.3.2.exe` พร้อม `latest.json` / `SHA256SUMS.txt`
## ทดสอบบนเครื่องแพ็ก

1. รัน `dist\PDFFormMarker\PDFFormMarker.exe`
2. ควรมีหน้าต่างสถานะ + เปิดเบราว์เซอร์ที่ `http://127.0.0.1:5000`
3. ตรวจว่ามี demo-form และสร้าง PDF ได้
4. ข้อมูลอยู่ที่ `%LOCALAPPDATA%\PDFFormMarker\`

## พฤติกรรม first-run

- สร้าง `%LOCALAPPDATA%\PDFFormMarker\data` และ `logs`
- สร้าง `secret_key` อัตโนมัติ
- seed demo ให้ผู้ใช้ `local`
- ไม่โหลด `.env` จากโฟลเดอร์ติดตั้ง (กัน `LICENSE_BYPASS`)

## ติดตั้งที่โรงเรียน

1. ส่ง `FormDD-Setup-*.exe`
2. ติดตั้ง (ไม่ต้องสิทธิ์แอดมิน — PrivilegesRequired=lowest)
3. เปิดจาก Desktop / Start Menu
4. คัดลอกรหัสเครื่องจากแถบไลเซนต์ (ปุ่มคัดลอก) → ส่งมาที่ formdd@xambrain.com เพื่อขอคีย์  
   นโยบาย: [SUPPORT.md](SUPPORT.md)

ถ้าโปรแกรมเก่ายังเปิดอยู่ Setup จะ**ปิดให้อัตโนมัติ**ก่อนคัดลอกไฟล์ทับ (และตอนถอนการติดตั้งด้วย) — ไม่ต้องปิดมือ

ถ้ายังทับไฟล์ไม่ได้ Setup อาจขอ**รีสตาร์ทเครื่อง** (ธง `restartreplace`) — หลังรีบูตเปิดแอปแล้วดูเลขเวอร์ชันมุมขวาบนให้ตรงกับ Setup

ถอนการติดตั้งไม่ลบโฟลเดอร์ AppData — สำรองด้วยปุ่มในแอปก่อนย้ายเครื่อง

ชื่อที่ลูกค้าเห็นคือ **FormDD-Setup-x.y.z.exe** (โฟลเดอร์ติดตั้งและ exe ภายในยังเป็น `PDFFormMarker` เพื่อให้อัปเกรดทับชุดเดิมได้)

## ปล่อยรุ่น

ไฟล์ `.exe` ตามเวอร์ชันเป็น immutable — ห้ามทับ `FormDD-Setup-0.3.2.exe` ด้วยไฟล์ใหม่  
อัปโหลดไฟล์ใหม่ + ทับแค่ `latest.json` บน `formdd.xambrain.com`  
สร้าง GitHub Release คู่ทุกครั้ง (`FormDD-Setup-x.y.z.exe` + `SHA256SUMS.txt`)

บน GitHub: ติดแท็ก `v0.3.2` (ต้องตรง `APP_VERSION` ใน `envutil.py`) แล้ว workflow **Release** จะแพ็กด้วย `scripts/build_windows.ps1` และสร้าง Release ให้  
รันมือได้จากแท็บ Actions → Release → Run workflow (ได้ artifact สำหรับอัปโหลด VPS โดยยังไม่เปิด Release)

รายละเอียด SHA-256, แคช Caddy, และของที่ห้ามวางใน `/var/www/formdd`: [UPDATE.md](UPDATE.md)

