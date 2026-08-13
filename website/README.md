# เว็บไซต์ FromDD

แผนดาวน์โหลดชุดเดียว + ราคา + Activate: [docs/SALES_LICENSE_PLAN.md](../docs/SALES_LICENSE_PLAN.md)  
นโยบายซัพพอร์ต: [docs/SUPPORT.md](../docs/SUPPORT.md)

- `index.html` — หน้าแรกภาษาไทย + คลิปสอน + ปุ่มดาวน์โหลด
- `en.html` — หน้าแรกภาษาอังกฤษ
- `pricing.html` / `pricing.en.html` — ราคาไทย (บาท) และต่างประเทศ (USD) คนละหน้า
- `app.html` — ทดลองมาร์คจุด / กรอกใบลา ในเบราว์เซอร์

ดาวน์โหลดชี้ไปที่ `releases/PDFFormMarker-Setup-*.exe`  
ถ้ามี `releases/latest.json` ปุ่มจะอัปเดต URL ตาม `setup_url` (คัดลอกจาก `releases/latest.example.json`)

อีเมลออกคีย์ชั่วคราว: fromdd@xambrain.com — เทมเพลตใน [docs/LICENSE_EMAIL.md](../docs/LICENSE_EMAIL.md)

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
