# Releases

**ตัวติดตั้งอยู่บน GitHub Releases ไม่ได้อยู่บนโฮสต์เว็บ** — ไฟล์ราว 33 MB เกินเพดาน
25 MiB ต่อไฟล์ของ Cloudflare Pages และ GitHub เก็บไฟล์ตามแท็กให้อยู่แล้ว

- `FormDD-Setup-x.y.z.exe` + `SHA256SUMS.txt` — asset ของรีลีสตามแท็ก `vx.y.z` **ห้ามทับของเดิม**
- `latest.json` — ไฟล์เดียวในโฟลเดอร์นี้ที่ถูก deploy จริง ชี้ว่ารุ่นปัจจุบันคือรุ่นไหนและโหลดได้ที่ไหน

## ห้ามแก้ `latest.json` ด้วยมือ

workflow `release.yml` เขียนให้เองตอนตัดแท็ก: build → `write_release_meta.py --url-base
https://github.com/<org>/<repo>/releases/download/<tag>` → แนบเป็น asset → commit ทับไฟล์นี้
กลับเข้า master แล้ว Pages deploy ต่อเอง

แก้มือเมื่อไรจะโดนทับตอนปล่อยรุ่นถัดไป และถ้า `sha256` ไม่ตรงไฟล์จริง แอปจะปฏิเสธ
ตัวติดตั้งหลังดาวน์โหลด (`update_core.py` ตรวจ hash ก่อนรันเสมอ)

`latest.example.json` เป็นตัวอย่างรูปแบบไว้ดูเฉย ๆ ไม่ได้ถูกใช้งาน

## ทำไมต้องเสิร์ฟจากโดเมนเรา ไม่ชี้ไป GitHub ตรง ๆ

เครื่องลูกค้าที่ติดตั้งไปแล้วอ่าน URL จาก `update_feed.url` ที่ฝังตอนติดตั้ง ซึ่งชี้
`https://formdd.xambrain.com/releases/latest.json` เปลี่ยนโดเมนหรือย้ายพาธไม่ได้

ทำเป็น redirect ไป GitHub ก็ไม่ได้ — asset ของ GitHub ไม่ส่ง `Access-Control-Allow-Origin`
ปุ่มดาวน์โหลดบนเว็บที่อ่านไฟล์นี้ด้วย `fetch()` จะโดน CORS บล็อก

## ตอนยังไม่มี `latest.json`

ปุ่มดาวน์โหลดจะตกไปที่หน้า `releases/latest` ของ GitHub ซึ่งชี้รุ่นล่าสุดเสมอ
ไม่ตายและไม่ค้างเวอร์ชัน แต่แอปที่ติดตั้งแล้วจะตรวจอัปเดตไม่ได้จนกว่าไฟล์นี้จะมี
— ตัดแท็กให้ workflow สร้างไฟล์นี้ก่อน แล้วค่อยย้าย DNS
