# Windows installer (CP4)

สร้างตัวติดตั้งสำหรับโรงเรียน: ติดตั้ง → ไอคอน → เปิดเบราว์เซอร์ โดยไม่ต้องรู้ Python

## สิ่งที่ได้

| ผลลัพธ์ | ความหมาย |
|---------|----------|
| `dist/PDFFormMarker/` | โฟลเดอร์รันได้จาก PyInstaller (one-folder) |
| `dist/installer/PDFFormMarker-Setup-0.1.0.exe` | ตัวติดตั้ง Inno Setup (ถ้ามี ISCC) |

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

ผลลัพธ์: `dist\PDFFormMarker\PDFFormMarker.exe` และ (ถ้ามี Inno) `dist\installer\PDFFormMarker-Setup-0.1.0.exe`
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

1. ส่ง `PDFFormMarker-Setup-*.exe`
2. ติดตั้ง (ไม่ต้องสิทธิ์แอดมิน — PrivilegesRequired=lowest)
3. เปิดจาก Desktop / Start Menu
4. คัดลอกรหัสเครื่องจากแอป → ขอคีย์จากผู้ขาย

ถอนการติดตั้งไม่ลบโฟลเดอร์ AppData — สำรองด้วยปุ่มในแอปก่อนย้ายเครื่อง
