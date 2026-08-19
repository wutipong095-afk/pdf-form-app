# Frontend (TypeScript)

UI หลักของ PDF Form Marker — **Vite + TypeScript**  
Backend ยังเป็น Python (Flask + PyMuPDF)

## คำสั่ง

```bash
cd frontend
npm install
npm run build    # → ../static/js/app.js
npm run dev      # http://localhost:5173 (proxy → Flask :5000)
npm test         # vitest (jsdom)
npm run test:watch
```

ต้องรัน `python app.py` คู่กันตอน `npm run dev`

ทั้งโปรเจกต์มีเทสสองชุด รันคนละคำสั่ง — `python -m pytest -q` ที่รากโปรเจกต์ (ฝั่ง Flask)
และ `npm test` ที่นี่ (ฝั่งเบราว์เซอร์) ควรรันทั้งคู่ก่อนเปิด PR

## โมดูล

| ไฟล์ | หน้าที่ |
|------|---------|
| `src/app.ts` | จุดเข้า + ผูก UI ทั้งหน้า |
| `src/api.ts` | fetch ไป Flask |
| `src/types.ts` | ชนิดข้อมูล API |
| `src/state.ts` | สถานะแอป |
| `src/license.ts` | แถบไลเซนต์ |
| `src/docs.ts` | รายการ PDF / เทมเพลต / อัปโหลด |
| `src/viewer.ts` | หน้า PDF + จุดมาร์ค |
| `src/fields.ts` | รายการฟิลด์ + ตารางค่า |
| `src/chat.ts` | แชทกรอกข้อมูล |
| `src/sheets.ts` | ใบงาน — ออโต้เซฟ เปิด/ทำซ้ำ/ลบ/นำเข้า/ส่งออก |
| `src/history.ts` | แถบงานเก่า — ใบงาน + PDF ที่พิมพ์แล้ว |
| `src/*.test.ts` | เทส vitest ของโมดูลนั้น |

`templates/index.html` เหลือแค่ HTML/CSS แล้วโหลด `static/js/app.js`

## เทส

`src/sheets.test.ts` กับ `src/history.test.ts` คุมพฤติกรรมที่เคยพังจริงมาแล้ว ไม่ใช่เคสสมมติ:
ผูกใบงานก่อนเปิดเอกสารสำเร็จ · ออโต้เซฟเอาชื่อเทมเพลตไปทับชื่อใบ · คำตอบที่กลับมาช้ากว่าการสลับใบ ·
ลบใบที่เปิดอยู่แล้วค้างที่สแนปช็อตที่ถูกเก็บกวาดไปแล้ว

ตัวจัดการคลิกในหน้านี้กลืน error ลง `alert()` เทสจึง stub `alert` ให้โยน error แทน
ไม่งั้นเทสจะผ่านทั้งที่โค้ดพังกลางทาง
