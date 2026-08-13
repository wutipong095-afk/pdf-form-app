# แจ้งอัปเดตโปรแกรม (ไม่บังคับออนไลน์)

**English:** [UPDATE.en.md](UPDATE.en.md)

แอปเช็กเวอร์ชันจากไฟล์ `latest.json` บนเว็บผู้ขาย  
ถ้าเน็ตไม่ได้ หรือยังไม่ตั้ง URL — ใช้งานปกติ ไม่ขึ้น error

## สิ่งที่ลูกค้าเห็น

แถบสีฟ้าใต้ header: มีเวอร์ชันใหม่ → ปุ่มเปิดลิงก์ดาวน์โหลด Setup  
ปิดแถบได้ (จำต่อเวอร์ชันนั้นในเบราว์เซอร์)

## ผู้ขายต้องเตรียม

1. อัปโหลด `PDFFormMarker-Setup-x.y.z.exe` ไปที่เว็บ/ไดรฟ์สาธารณะ
2. อัปโหลด `latest.json` (ดูตัวอย่าง `docs/latest.example.json`)
3. บอกแอปว่า feed อยู่ที่ไหน อย่างใดอย่างหนึ่ง:

| วิธี | รายละเอียด |
|------|------------|
| ไฟล์ `update_feed.url` | วางข้าง `PDFFormMarker.exe` หรือ `%LOCALAPPDATA%\PDFFormMarker\` — เนื้อหาเป็น URL หนึ่งบรรทัด |
| env `UPDATE_CHECK_URL` | ใช้ตอนพัฒนา / ถ้าตั้งค่าได้ |

ตัวอย่าง `update_feed.url`:

```text
https://your-site.com/releases/latest.json
```

## รูปแบบ latest.json

```json
{
  "version": "0.2.0",
  "setup_url": "https://your-site.com/releases/PDFFormMarker-Setup-0.2.0.exe",
  "notes": "ข้อความสั้นอธิบาย",
  "published_at": "2026-07-26"
}
```

- `version` ต้องใหม่กว่าในแอป (เทียบแบบ semver ตัวเลข)
- `setup_url` เปิดในเบราว์เซอร์ให้ลูกค้าโหลดแล้วรัน Setup ทับของเดิม

## พฤติกรรมเทคนิค

- timeout ดึง feed ~3 วินาที
- แคชผลในหน่วยความจำ 6 ชั่วโมง
- `GET /api/update-check` · `?force=1` บังคับเช็กใหม่
- ไม่ดาวน์โหลด/ติดตั้งให้อัตโนมัติ — ลูกค้ารัน Setup เอง (ปิดโปรแกรมเก่าระหว่างติดตั้งมีใน Setup แล้ว)
