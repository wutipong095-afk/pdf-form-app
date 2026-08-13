# Changelog

## Unreleased
- แพ็กเกจ desktop แยก Linux (`.tar.gz`) / macOS (`.app` + `.dmg`) — `scripts/build_linux.sh` · `scripts/build_macos.sh`
- ข้อมูล frozen บน macOS/Linux เก็บใต้ Application Support / XDG ไม่ใช่ในโฟลเดอร์ติดตั้ง

## 0.2.0
- UI สลับภาษาไทย / English ในแอปเดียว (ค่าเริ่มต้นไทย)
- Catalog รวมศูนย์ `locales/th.json` + `locales/en.json` · `i18n_core` · frontend `t()`
- จำภาษาด้วย cookie + `%LOCALAPPDATA%\PDFFormMarker\data\ui_lang.txt` (launcher ตามด้วย)
- แปลข้อความ API / license / launcher ที่ผู้ใช้เห็น
- คู่มืออังกฤษ: `README.en.md`, `docs/BACKUP.en.md`, `docs/INSTALLER.en.md`, `docs/UPDATE.en.md`
- Installer: wizard English เสมอ · Thai เมื่อมี `Languages\Thai.isl`

## 0.1.9
- Hardening ความปลอดภัย: CSRF, Host check บน loopback, security headers, rate-limit login
- ตรวจ PDF อัปโหลด (magic/%PDF, หน้าสูงสุด, ไม่รองรับรหัสผ่าน)
- สำรอง/กู้: จำกัดขนาด·จำนวนไฟล์·compression ratio·path allowlist
- จำกัด API จัดการเครื่อง (ไลเซนต์, คลัง, สำรอง, โฟลเดอร์, รายงาน) ให้ admin
- launcher บังคับ `HOST=127.0.0.1` ในแพ็กเกจ desktop
- อัปเดต feed/`setup_url` รับเฉพาะ HTTPS
- Dockerfile คัดลอก `update_core.py` ให้ container บูตได้; เอกสารระบุ Docker เป็นโหมดขั้นสูง

## 0.1.8
- Seed `demo-form.pdf` เฉพาะตอน「ใช้ค่าแนะนำ」— ไม่ใส่ในโฟลเดอร์ว่างที่ผู้ใช้เลือกเอง
- เลือกโฟลเดอร์คลังแบบ async (ไม่บล็อก worker) + กันกดซ้ำ
- ข้อความติดตั้งเรื่องรีสตาร์ท/`restartreplace` และตรวจเวอร์ชันในแอป

## 0.1.7
- คลังเอกสารแสดงเมื่อกดเรียกใช้เท่านั้น
- ซ่อนปุ่มโฟลเดอร์ข้อมูล (AppData) จาก UI
- Setup ปิดโปรแกรมเก่าระหว่างอัปเกรด; เลขอาราบิกเป็นค่าเริ่มต้น; เลือกโฟลเดอร์คลังได้
