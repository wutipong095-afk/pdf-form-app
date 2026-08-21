# เว็บไซต์ FormDD

แผนดาวน์โหลดชุดเดียว + ราคา + Activate: [docs/SALES_LICENSE_PLAN.md](../docs/SALES_LICENSE_PLAN.md)  
นโยบายซัพพอร์ต: [docs/SUPPORT.md](../docs/SUPPORT.md)

- `index.html` — หน้าแรกภาษาไทย: ปักฟอร์มครั้งเดียว กรอกซ้ำ ข้อมูลอยู่ในเครื่อง
- `en.html` — หน้าแรกภาษาอังกฤษ (จุดขายเดียวกัน, ราคา $49 จ่ายครั้งเดียว)
- `pricing.html` — ราคาไทย 1/3/5/10 ปี + คิวอาร์พร้อมเพย์ (`img/promptpay-qr.png` ต้องอยู่ในเรป ห้าม deploy ขาดไฟล์นี้)
- `pricing.en.html` — Personal $49 / School $99–149 / Org จาก $249 ไม่โชว์ราคาบาท
- `app.html` — ทดลองมาร์คจุด / กรอกใบลา ในเบราว์เซอร์

ดาวน์โหลดชี้ไปที่ `releases/FormDD-Setup-*.exe` (ห้ามใช้ชื่อ `FormDD-Setup.exe` แล้วทับ)  
ถ้ามี `releases/latest.json` ปุ่มจะอัปเดต URL ตาม `setup_url` (มี `sha256` / `size` — คัดลอกจาก `releases/latest.example.json` หรือไฟล์ที่ build เขียนให้)

`latest.json` ต้องไม่ถูกแคชนาน (Caddy `Cache-Control: no-cache`) · ไฟล์ `.exe` ตามเวอร์ชันแคชยาวได้เพราะ immutable

GitHub Release สร้างคู่ทุกครั้งเป็นสำเนา — โฮสต์หลักยังเป็น formdd.xambrain.com  
ห้ามวาง private key / `gen_license.py` / `.env` ใน `/var/www/formdd` — ดู [docs/UPDATE.md](../docs/UPDATE.md)

อีเมลออกคีย์ชั่วคราว: formdd@xambrain.com — เทมเพลตใน [docs/LICENSE_EMAIL.md](../docs/LICENSE_EMAIL.md)

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
