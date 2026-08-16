# แจ้งอัปเดตโปรแกรม (ไม่บังคับออนไลน์)

**English:** [UPDATE.en.md](UPDATE.en.md)

แอปเช็กเวอร์ชันจากไฟล์ `latest.json` บนเว็บผู้ขาย  
ถ้าเน็ตไม่ได้ หรือยังไม่ตั้ง URL — ใช้งานปกติ ไม่ขึ้น error

โฮสต์หลักของ FromDD: `https://fromdd.xambrain.com/releases/latest.json`  
ชุดติดตั้งใส่ `update_feed.url` ให้อัตโนมัติ

## สิ่งที่ลูกค้าเห็น

แถบสีฟ้าใต้ header: มีเวอร์ชันใหม่ → ปุ่ม **ติดตั้ง** (ดาวน์โหลด ตรวจ SHA-256 แล้วเปิด Setup)  
ลิงก์เปิดในเบราว์เซอร์ยังมีเป็นทางสำรอง  
ปิดแถบได้ (จำต่อเวอร์ชันนั้นในเบราว์เซอร์)

## ผู้ขายต้องเตรียม

1. บิวด์แล้วได้ออกมาที่ `dist/installer/`:
   - `FromDD-Setup-x.y.z.exe` (ห้ามใช้ชื่อ `FromDD-Setup.exe` แล้วทับ)
   - `latest.json` (มี `sha256` / `size`)
   - `SHA256SUMS.txt`
2. อัปโหลด **ไฟล์ .exe ใหม่** ไปที่ `/var/www/fromdd/releases/` — **ห้ามทับ** `FromDD-Setup-x.y.z.exe` ของรุ่นเก่า
3. อัปโหลด `latest.json` ทับตัวเดิม (ไฟล์นี้ชี้รุ่นใหม่ได้)
4. สร้าง GitHub Release คู่ทุกครั้ง (สำเนา + ประวัติ) — ดูด้านล่าง

## รูปแบบ latest.json

```json
{
  "version": "0.3.1",
  "setup_url": "https://fromdd.xambrain.com/releases/FromDD-Setup-0.3.1.exe",
  "sha256": "abcdef....64 hex....",
  "size": 34603008,
  "published_at": "2026-08-13",
  "notes": "ข้อความสั้นอธิบาย"
}
```

- `version` ต้องใหม่กว่าในแอป (เทียบแบบ semver ตัวเลข)
- `setup_url` ต้องเป็น HTTPS และชื่อไฟล์ต้องตรงเวอร์ชัน เช่น `FromDD-Setup-0.3.1.exe`
- `sha256` จำเป็นถ้าจะให้แอปติดตั้งจากปุ่มในแอป (ตรวจก่อนรัน)
- `size` แนะนำ — ถ้ามี แอปจะเทียบขนาดไฟล์ด้วย
- ตัวอย่างเต็ม: `docs/latest.example.json` / `website/releases/latest.example.json`

หลัง Inno, `scripts/build_windows.ps1` เรียก `scripts/write_release_meta.py` ให้แล้ว

## ไฟล์ตามเวอร์ชันเป็น immutable

ถูก:

```text
FromDD-Setup-0.3.0.exe
FromDD-Setup-0.3.1.exe
FromDD-Setup-0.4.0.exe
```

ไม่ถูก: `FromDD-Setup.exe` หรือ `PDFFormMarker-Setup.exe` แล้วเอาไฟล์ใหม่ไปทับ

ถ้าลูกค้าบอกว่า “0.3.0 มีปัญหา” ต้องย้อนไปตรวจ installer ตัวนั้นได้  
`latest.json` เท่านั้นที่เปลี่ยนไปชี้รุ่นใหม่

ชื่อภายใน repo / โฟลเดอร์ติดตั้งยังเป็น `PDFFormMarker` ได้ (`PDFFormMarker.exe`, `%LOCALAPPDATA%\PDFFormMarker`) — สิ่งที่ลูกค้าดาวน์โหลดคือ **FromDD**

## Caddy (แคช)

```text
/releases/latest.json
Cache-Control: no-cache

/releases/FromDD-Setup-0.3.0.exe
Cache-Control: public, max-age=31536000, immutable
```

หลักการ: `latest.json` เปลี่ยนบ่อย · `.exe` ตามเวอร์ชันไม่ควรเปลี่ยนอีกเลย  
ตัวอย่าง config: `website/Caddyfile.fromdd`

แอปดึง feed ด้วย `Cache-Control: no-cache` และ timeout ~3 วินาที

## GitHub Releases (ทำทุกครั้ง — สำเนา ไม่ใช่โฮสต์หลัก)

เว็บหลักยังเป็น `fromdd.xambrain.com`  
ทุกครั้งที่ปล่อยรุ่น ให้สร้าง GitHub Release คู่ด้วย เช่น tag `v0.3.1` ชื่อ **FromDD v0.3.1**

Assets:

- `FromDD-Setup-0.3.1.exe`
- `SHA256SUMS.txt`

ประโยชน์: ประวัติ, tag, release notes, binary สำรอง, หลักฐานว่าเวอร์ชันนั้นเคยถูกปล่อย, ดาวน์โหลดสำรองถ้า VPS มีปัญหา

ตัวอย่าง:

```powershell
gh release create v0.3.1 `
  dist/installer/FromDD-Setup-0.3.1.exe `
  dist/installer/SHA256SUMS.txt `
  --title "FromDD v0.3.1" `
  --notes-file CHANGELOG.md
```

อย่าให้ GitHub เป็น URL ใน `latest.json` เป็นค่าเริ่มต้น — ชี้ที่ fromdd.xambrain.com

## คีย์และของลับ — ห้ามอยู่บนเว็บสาธารณะ

`/var/www/fromdd` ใส่ได้: HTML, CSS, JS, installer, `latest.json`

ห้ามวาง: `private.key`, `license-master.key`, `gen_license.py`, `.env`, ฐานข้อมูลลูกค้า

ถ้ามี Activate ออนไลน์ในอนาคต ให้แยกเป็น `api.fromdd.xambrain.com` (หรือ `/api` ผ่าน reverse proxy)  
private key อยู่ใน environment/secret ของ backend เท่านั้น

## พฤติกรรมเทคนิค

- timeout ดึง feed ~3 วินาที · ดาวน์โหลด Setup ~180 วินาที
- แคชผลในหน่วยความจำ 6 ชั่วโมง
- `GET /api/update-check` · `?force=1` บังคับเช็กใหม่
- `POST /api/update-install` — ดาวน์โหลดลง `%LOCALAPPDATA%\PDFFormMarker\data\updates\` ตรวจ SHA-256 แล้วเปิด Setup (เฉพาะ localhost หลังผู้ใช้กดปุ่ม)
- ถ้าฟีดไม่มี `sha256` แอปจะไม่รันไฟล์ให้ — เหลือแค่ลิงก์เบราว์เซอร์
