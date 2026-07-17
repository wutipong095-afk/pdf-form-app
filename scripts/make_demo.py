"""สร้าง demo PDF + เทมเพลต (รันเมื่อต้องการสร้างใหม่)"""
import json
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[1]
UPLOADS = ROOT / "demo" / "uploads"
TPL = ROOT / "demo" / "templates_json"
UPLOADS.mkdir(parents=True, exist_ok=True)
TPL.mkdir(parents=True, exist_ok=True)

pdf_path = UPLOADS / "demo-form.pdf"
doc = fitz.open()
page = doc.new_page(width=595, height=842)
page.draw_rect(fitz.Rect(0, 0, 595, 70), color=(0.10, 0.24, 0.43), fill=(0.10, 0.24, 0.43))
page.insert_text((40, 45), "Demo Form - PDF Form Marker", fontsize=18, color=(1, 1, 1), fontname="helv")
for label, y in [("Name", 100), ("Organization", 150), ("Date", 200), ("Details", 250)]:
    page.insert_text((40, y), label + ":", fontsize=11, fontname="helv", color=(0.25, 0.25, 0.25))
    page.draw_line(fitz.Point(150, y + 2), fitz.Point(540, y + 2), color=(0.55, 0.55, 0.55), width=0.8)
page.draw_line(fitz.Point(40, 290), fitz.Point(540, 290), color=(0.55, 0.55, 0.55), width=0.8)
page.insert_text((40, 340), "Amount (THB):", fontsize=11, fontname="helv", color=(0.25, 0.25, 0.25))
page.draw_line(fitz.Point(150, 342), fitz.Point(300, 342), color=(0.55, 0.55, 0.55), width=0.8)
page.insert_text((40, 420), "Requester:", fontsize=11, fontname="helv", color=(0.25, 0.25, 0.25))
page.draw_line(fitz.Point(120, 422), fitz.Point(260, 422), color=(0.55, 0.55, 0.55), width=0.8)
page.insert_text((320, 420), "Approver:", fontsize=11, fontname="helv", color=(0.25, 0.25, 0.25))
page.draw_line(fitz.Point(400, 422), fitz.Point(540, 422), color=(0.55, 0.55, 0.55), width=0.8)
page.insert_text(
    (40, 800),
    "Sample form bundled with the app. Safe to redistribute.",
    fontsize=9,
    fontname="helv",
    color=(0.5, 0.5, 0.5),
)
doc.save(pdf_path)
doc.close()

fields = [
    {"name": "ชื่อ-นามสกุล", "page": 0, "x": 155, "y": 100, "size": 14, "value": ""},
    {"name": "หน่วยงาน", "page": 0, "x": 155, "y": 150, "size": 14, "value": ""},
    {"name": "วันที่", "page": 0, "x": 155, "y": 200, "size": 14, "value": ""},
    {"name": "รายละเอียด", "page": 0, "x": 40, "y": 270, "size": 13, "value": ""},
    {"name": "จำนวนเงิน", "page": 0, "x": 155, "y": 340, "size": 14, "value": ""},
    {"name": "ผู้ขอ", "page": 0, "x": 125, "y": 420, "size": 14, "value": ""},
    {"name": "ผู้อนุมัติ", "page": 0, "x": 405, "y": 420, "size": 14, "value": ""},
]
(TPL / "demo-ใบเบิก.json").write_text(
    json.dumps({"doc": "demo-form.pdf", "fields": fields}, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
print("wrote", pdf_path)
