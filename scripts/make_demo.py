"""สร้าง PDF + เทมเพลตแพ็กทดลอง (รันเมื่อต้องการสร้างใหม่)

  python scripts/make_demo.py

ออกไฟล์ใน demo/uploads และ demo/templates_json — seed เข้าเครื่องผู้ใช้ตอนเปิดแอป
"""
from __future__ import annotations

import json
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[1]
UPLOADS = ROOT / "demo" / "uploads"
TPL = ROOT / "demo" / "templates_json"
NAVY = (0.10, 0.24, 0.43)


def _fontfile() -> str | None:
    candidates: list[Path] = []
    fonts_dir = ROOT / "fonts"
    if fonts_dir.is_dir():
        candidates.extend(fonts_dir.glob("THSarabun*.ttf"))
    candidates.extend(
        [
            Path(r"C:\Windows\Fonts\LeelawUI.ttf"),
            Path(r"C:\Windows\Fonts\tahoma.ttf"),
            Path("/usr/share/fonts/truetype/noto/NotoSansThai-Regular.ttf"),
        ]
    )
    for p in candidates:
        if p.is_file() and "Bold" not in p.name and "Italic" not in p.name:
            return str(p)
    return None


def _text(
    page: fitz.Page,
    xy: tuple[float, float],
    text: str,
    size: float = 11,
    color: tuple[float, float, float] = (0.25, 0.25, 0.25),
    *,
    fontname: str = "helv",
) -> None:
    fontfile = _fontfile() if fontname == "th" else None
    kwargs: dict = {"fontsize": size, "color": color}
    if fontfile:
        kwargs["fontfile"] = fontfile
        kwargs["fontname"] = "th"
    else:
        kwargs["fontname"] = "helv"
    page.insert_text(xy, text, **kwargs)


def _line(page: fitz.Page, x0: float, y: float, x1: float) -> None:
    page.draw_line(
        fitz.Point(x0, y + 2),
        fitz.Point(x1, y + 2),
        color=(0.55, 0.55, 0.55),
        width=0.8,
    )


def _save_tpl(name: str, doc: str, fields: list[dict]) -> Path:
    path = TPL / name
    path.write_text(
        json.dumps({"doc": doc, "fields": fields}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def make_requisition(*, overwrite: bool = False) -> Path:
    """ใบเบิกตัวอย่าง — ป้ายอังกฤษ ฟิลด์ไทย (ของเดิม)

    อย่าทับไฟล์ที่มีอยู่แล้วโดยไม่ตั้งใจ — hash ใช้ตรวจโหมดทดลอง
    """
    pdf_path = UPLOADS / "demo-form.pdf"
    tpl_path = TPL / "demo-ใบเบิก.json"
    if pdf_path.is_file() and tpl_path.is_file() and not overwrite:
        return pdf_path
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.draw_rect(fitz.Rect(0, 0, 595, 70), color=NAVY, fill=NAVY)
    page.insert_text(
        (40, 45), "Demo Form - PDF Form Marker", fontsize=18, color=(1, 1, 1), fontname="helv"
    )
    for label, y in [("Name", 100), ("Organization", 150), ("Date", 200), ("Details", 250)]:
        page.insert_text((40, y), label + ":", fontsize=11, fontname="helv", color=(0.25, 0.25, 0.25))
        _line(page, 150, y, 540)
    page.draw_line(fitz.Point(40, 290), fitz.Point(540, 290), color=(0.55, 0.55, 0.55), width=0.8)
    page.insert_text((40, 340), "Amount (THB):", fontsize=11, fontname="helv", color=(0.25, 0.25, 0.25))
    _line(page, 150, 340, 300)
    page.insert_text((40, 420), "Requester:", fontsize=11, fontname="helv", color=(0.25, 0.25, 0.25))
    _line(page, 120, 420, 260)
    page.insert_text((320, 420), "Approver:", fontsize=11, fontname="helv", color=(0.25, 0.25, 0.25))
    _line(page, 400, 420, 540)
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
    _save_tpl("demo-ใบเบิก.json", "demo-form.pdf", fields)
    return pdf_path


def make_leave() -> Path:
    """ใบลาตัวอย่าง (ไทย)"""
    pdf_path = UPLOADS / "demo-leave.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.draw_rect(fitz.Rect(0, 0, 595, 70), color=NAVY, fill=NAVY)
    thai = "th" if _fontfile() else "helv"
    _text(page, (40, 32), "ใบลา" if thai == "th" else "Leave request", 20, (1, 1, 1), fontname=thai)
    _text(page, (40, 52), "PDF Form Marker", 11, (1, 1, 1), fontname="helv")
    page.insert_text((400, 45), "FromDD", fontsize=14, color=(1, 1, 1), fontname="helv")

    fields: list[dict] = []

    def blank(name: str, x: float, y: float, x1: float, size: float = 14) -> None:
        _line(page, x, y, x1)
        fields.append({"name": name, "page": 0, "x": x + 4, "y": y, "size": size, "value": ""})

    def label(xy: tuple[float, float], text: str, size: float = 11) -> None:
        _text(page, xy, text, size, fontname=thai)

    label((40, 100), "หน่วยงาน" if thai == "th" else "Office")
    blank("หน่วยงาน", 110, 100, 540)

    label((40, 140), "ที่" if thai == "th" else "No.")
    blank("ที่", 70, 140, 250)
    label((280, 140), "เขียนที่" if thai == "th" else "Written at")
    blank("เขียนที่", 340, 140, 540)

    label((40, 180), "วันที่" if thai == "th" else "Date")
    blank("วันที่", 80, 180, 280)

    label((40, 220), "เรื่อง ขออนุญาตลา" if thai == "th" else "Subject: leave request")
    label((40, 255), "เรียน" if thai == "th" else "To")
    blank("เรียน", 80, 255, 540)

    label((40, 300), "ข้าพเจ้า" if thai == "th" else "I,")
    blank("ชื่อ-นามสกุล", 100, 300, 300)
    label((320, 300), "ตำแหน่ง" if thai == "th" else "Position")
    blank("ตำแหน่ง", 380, 300, 540)

    label((40, 340), "สังกัด" if thai == "th" else "Department")
    blank("สังกัด", 90, 340, 540)

    label((40, 385), "ประเภทการลา" if thai == "th" else "Leave type")
    blank("ประเภทการลา", 130, 385, 280)
    label((300, 385), "เนื่องจาก" if thai == "th" else "Reason")
    blank("เนื่องจาก", 360, 385, 540)

    label((40, 430), "ตั้งแต่วันที่" if thai == "th" else "From")
    blank("ตั้งแต่วันที่", 120, 430, 260)
    label((280, 430), "ถึงวันที่" if thai == "th" else "To date")
    blank("ถึงวันที่", 340, 430, 540)

    label((40, 470), "รวม" if thai == "th" else "Total")
    blank("จำนวนวัน", 80, 470, 160)
    label((165, 470), "วัน" if thai == "th" else "days")

    label((40, 510), "ติดต่อระหว่างลา" if thai == "th" else "Contact while away")
    blank("ติดต่อระหว่างลา", 150, 510, 540)

    _text(
        page,
        (40, 800),
        "แบบตัวอย่างใน FromDD — ทดลองได้โดยไม่ต้องมีไลเซนต์",
        9,
        (0.5, 0.5, 0.5),
        fontname=thai,
    )
    doc.save(pdf_path)
    doc.close()
    _save_tpl("demo-ใบลา.json", "demo-leave.pdf", fields)
    return pdf_path


def make_request() -> Path:
    """Leave / request form (English) for international trial"""
    pdf_path = UPLOADS / "demo-request.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.draw_rect(fitz.Rect(0, 0, 595, 70), color=NAVY, fill=NAVY)
    page.insert_text((40, 32), "Leave / request form", fontsize=20, color=(1, 1, 1), fontname="helv")
    page.insert_text((40, 52), "PDF Form Marker — FromDD sample", fontsize=11, color=(1, 1, 1), fontname="helv")

    fields: list[dict] = []

    def blank(name: str, x: float, y: float, x1: float, size: float = 14) -> None:
        _line(page, x, y, x1)
        fields.append({"name": name, "page": 0, "x": x + 4, "y": y, "size": size, "value": ""})

    def label(xy: tuple[float, float], text: str) -> None:
        page.insert_text(xy, text, fontsize=11, fontname="helv", color=(0.25, 0.25, 0.25))

    label((40, 100), "Organization")
    blank("Organization", 130, 100, 540)

    label((40, 140), "Request no.")
    blank("Request no.", 120, 140, 280)
    label((300, 140), "Date")
    blank("Date", 340, 140, 540)

    label((40, 180), "To")
    blank("To", 70, 180, 540)

    label((40, 220), "Full name")
    blank("Full name", 110, 220, 320)
    label((340, 220), "Position")
    blank("Position", 400, 220, 540)

    label((40, 260), "Department")
    blank("Department", 120, 260, 540)

    label((40, 310), "Type")
    blank("Type", 80, 310, 250)
    label((270, 310), "Reason")
    blank("Reason", 330, 310, 540)

    label((40, 360), "From")
    blank("From", 80, 360, 250)
    label((270, 360), "Until")
    blank("Until", 320, 360, 540)

    label((40, 410), "Total days")
    blank("Total days", 110, 410, 200)

    label((40, 460), "Contact while away")
    blank("Contact while away", 160, 460, 540)

    label((40, 530), "Requester")
    blank("Requester", 110, 530, 280)
    label((300, 530), "Approver")
    blank("Approver", 370, 530, 540)

    page.insert_text(
        (40, 800),
        "Sample form bundled with FromDD. Trial use does not require a license.",
        fontsize=9,
        fontname="helv",
        color=(0.5, 0.5, 0.5),
    )
    doc.save(pdf_path)
    doc.close()
    _save_tpl("demo-request.json", "demo-request.pdf", fields)
    return pdf_path


def main() -> None:
    UPLOADS.mkdir(parents=True, exist_ok=True)
    TPL.mkdir(parents=True, exist_ok=True)
    paths = (make_requisition(), make_leave(), make_request())
    for p in paths:
        print("wrote", p)


if __name__ == "__main__":
    main()
