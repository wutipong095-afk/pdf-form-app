# เว็บไซต์ FormDD

แผนดาวน์โหลดชุดเดียว + ราคา + Activate: [docs/SALES_LICENSE_PLAN.md](../docs/SALES_LICENSE_PLAN.md)  
นโยบายซัพพอร์ต: [docs/SUPPORT.md](../docs/SUPPORT.md)

- `index.html` — หน้าแรกภาษาไทย: ปักฟอร์มครั้งเดียว กรอกซ้ำ ข้อมูลอยู่ในเครื่อง
- `en.html` — หน้าแรกภาษาอังกฤษ (จุดขายเดียวกัน, ราคา $49 จ่ายครั้งเดียว)
- `pricing.html` — ราคาไทย 1/3/5/10 ปี + คิวอาร์พร้อมเพย์ (`img/promptpay-qr.png` ต้องอยู่ในเรป ห้าม deploy ขาดไฟล์นี้)
- `pricing.en.html` — Personal $49 / School $99–149 / Org จาก $249 ไม่โชว์ราคาบาท
- `app.html` — ทดลองมาร์คจุด / กรอกใบลา ในเบราว์เซอร์

ปุ่มดาวน์โหลดชี้หน้า `releases/latest` ของ GitHub เป็นค่าตั้งต้น — ชี้รุ่นล่าสุดเสมอ ไม่ค้างเวอร์ชัน  
ถ้ามี `releases/latest.json` ปุ่มจะสลับเป็นลิงก์ตรงไป asset บน GitHub พร้อมเลขเวอร์ชัน — ไฟล์นั้น workflow เขียนให้ ห้ามแก้มือ ดู [releases/README.md](releases/README.md)

`latest.json` ต้องไม่ถูกแคชนาน — กติกานี้อยู่ใน `_headers` (โฮสต์ปัจจุบัน) และ `Caddyfile.formdd` (อ้างอิงตอนรันบน VPS)

ตัวติดตั้งอยู่บน GitHub Releases · โฮสต์นี้เสิร์ฟแค่หน้าเว็บกับ `releases/latest.json`  
ห้ามวาง private key / `gen_license.py` / `.env` ใน `/var/www/formdd` — ดู [docs/UPDATE.md](../docs/UPDATE.md)

อีเมลออกคีย์ชั่วคราว: formdd@xambrain.com — เทมเพลตใน [docs/LICENSE_EMAIL.md](../docs/LICENSE_EMAIL.md)

## Deploy (Cloudflare Pages)

โปรเจกต์ Pages ผูกกับ `wutipong095-afk/pdf-form-app` โดยตั้ง:

- **Build command** = เว้นว่าง · **Framework preset** = None (ไฟล์ static ล้วน)
- **Build output directory** = `website` — ถ้าไม่ตั้ง Pages จะ deploy รากเรปซึ่งเป็นแอป Python
- **Domain** = `formdd.xambrain.com` — ห้ามเปลี่ยนโดเมน เครื่องลูกค้าที่ติดตั้งไปแล้วอ่าน URL อัปเดตจากไฟล์ `update_feed.url` ที่ฝังตอนติดตั้ง

`_headers` ต้องอยู่ใน build output directory (คือโฟลเดอร์นี้) ถึงจะมีผล

**ตัวติดตั้งไม่ได้อยู่บนโฮสต์นี้** — Pages จำกัดไฟล์ละ 25 MiB ส่วน Setup ราว 33 MB
ตัวติดตั้งจึงอยู่บน GitHub Releases และ `releases/latest.json` เป็นตัวชี้ทาง
**ลำดับตอนย้ายโฮสต์** — ห้ามสลับ:

1. ตัดแท็ก `vx.y.z` ให้ `release.yml` สร้าง GitHub Release และ commit `releases/latest.json` เข้ามา
2. ตรวจว่าเครื่องที่ติดตั้งรุ่นเดิมอยู่ กดตรวจอัปเดตแล้วเจอรุ่นใหม่ ดาวน์โหลดผ่าน sha256 ตรง
3. ย้าย DNS มาที่ Pages
4. ปิด `/var/www/formdd` บน VPS เป็นขั้นสุดท้าย

ย้าย DNS ก่อนมี `latest.json` = เครื่องลูกค้าตรวจอัปเดตไม่ได้ (404) จนกว่าจะตัดแท็ก
## ใส่คลิป YouTube จริง

เปิด `js/site.js` แก้บรรทัด:

```js
const YOUTUBE_ID = "";
```

เป็นรหัสหลัง `v=` เช่น `AbCdEfGhIjK` จาก `https://www.youtube.com/watch?v=AbCdEfGhIjK`

## เปิดดูในเครื่อง

```bash
python -m http.server 8080 --directory website
```

http://127.0.0.1:8080
