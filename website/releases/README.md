# Releases (immutable)

โฮสต์หลัก: `https://fromdd.xambrain.com/releases/`

วางบน VPS ที่ `/var/www/fromdd/releases/`:

- `FromDD-Setup-x.y.z.exe` — ไฟล์ตามเวอร์ชัน **ห้ามทับของเดิม**
- `latest.json` — ชี้รุ่นปัจจุบัน (ไฟล์นี้ทับได้) คัดลอกจาก `latest.example.json` หรือใช้ไฟล์ที่ `scripts/write_release_meta.py` เขียนให้หลัง build
- `SHA256SUMS.txt` — สำเนา checksum สำหรับ GitHub Release

ผิด: `FromDD-Setup.exe` แล้วเอาไฟล์ใหม่ไปทับตลอด  
ถูก: `FromDD-Setup-0.3.0.exe`, `FromDD-Setup-0.3.1.exe`, `FromDD-Setup-0.4.0.exe`

ปุ่มดาวน์โหลดบนเว็บอ่าน `latest.json` ถ้ามี ไม่งั้นชี้ `FromDD-Setup-0.3.1.exe`

Caddy: `latest.json` = `Cache-Control: no-cache` · `.exe` = cache ยาว immutable — ดู `website/Caddyfile.fromdd`

ทุกครั้งที่ปล่อยรุ่น ให้สร้าง GitHub Release คู่ด้วย (สำเนา + ประวัติ) แต่เว็บหลักยังเป็น fromdd.xambrain.com
