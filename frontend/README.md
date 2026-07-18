# Frontend (TypeScript)

UI หลักของ PDF Form Marker — **Vite + TypeScript**  
Backend ยังเป็น Python (Flask + PyMuPDF)

## คำสั่ง

```bash
cd frontend
npm install
npm run build    # → ../static/js/app.js
npm run dev      # http://localhost:5173 (proxy → Flask :5000)
```

ต้องรัน `python app.py` คู่กันตอน `npm run dev`

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

`templates/index.html` เหลือแค่ HTML/CSS แล้วโหลด `static/js/app.js`
