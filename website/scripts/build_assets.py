"""สร้าง PDF + PNG หน้าเดโมให้เว็บ FormDD หน้าตาเดียวกับโปรแกรม"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "website"
PAGES = OUT / "pages"
FORMS = OUT / "forms"
TPL_DIR = OUT / "data" / "templates"
ZOOM = 2.0
FONT = Path(r"C:\Windows\Fonts\LeelawUI.ttf")
NAVY = (0.10, 0.24, 0.43)


def _fontfile() -> str | None:
    if FONT.exists():
        return str(FONT)
    return None


def _text(page: fitz.Page, xy: tuple[float, float], text: str, size: float = 11, color=(0.2, 0.2, 0.2)) -> None:
    fontfile = _fontfile()
    kwargs = {"fontsize": size, "color": color}
    if fontfile:
        kwargs["fontfile"] = fontfile
        kwargs["fontname"] = "th"
    else:
        kwargs["fontname"] = "helv"
    page.insert_text(xy, text, **kwargs)


def _line(page: fitz.Page, x0: float, y: float, x1: float) -> None:
    page.draw_line(fitz.Point(x0, y + 2), fitz.Point(x1, y + 2), color=(0.55, 0.55, 0.55), width=0.8)


def make_demo() -> tuple[Path, list[dict]]:
    path = FORMS / "demo-form.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.draw_rect(fitz.Rect(0, 0, 595, 70), color=NAVY, fill=NAVY)
    page.insert_text((40, 45), "Demo Form - PDF Form Marker", fontsize=18, color=(1, 1, 1), fontname="helv")
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
    doc.save(path)
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
    return path, fields


def make_leave() -> tuple[Path, list[dict]]:
    path = FORMS / "leave.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.draw_rect(fitz.Rect(0, 0, 595, 70), color=NAVY, fill=NAVY)
    _text(page, (40, 32), "ใบลา", 20, (1, 1, 1))
    _text(page, (40, 52), "PDF Form Marker", 11, (1, 1, 1))
    _text(page, (400, 45), "FormDD", 14, (1, 1, 1))

    fields: list[dict] = []

    def blank(name: str, x: float, y: float, x1: float, size: float = 14) -> None:
        _line(page, x, y, x1)
        fields.append({"name": name, "page": 0, "x": x + 4, "y": y, "size": size, "value": ""})

    _text(page, (40, 100), "หน่วยงาน")
    blank("หน่วยงาน", 110, 100, 540)

    _text(page, (40, 140), "ที่")
    blank("ที่", 70, 140, 250)
    _text(page, (280, 140), "เขียนที่")
    blank("เขียนที่", 340, 140, 540)

    _text(page, (40, 180), "วันที่")
    blank("วันที่", 80, 180, 280)

    _text(page, (40, 220), "เรื่อง ขออนุญาตลา")
    _text(page, (40, 255), "เรียน")
    blank("เรียน", 80, 255, 540)

    _text(page, (40, 300), "ข้าพเจ้า")
    blank("ชื่อ-นามสกุล", 100, 300, 300)
    _text(page, (320, 300), "ตำแหน่ง")
    blank("ตำแหน่ง", 380, 300, 540)

    _text(page, (40, 340), "สังกัด")
    blank("สังกัด", 90, 340, 540)

    _text(page, (40, 385), "ประเภทการลา")
    blank("ประเภทการลา", 130, 385, 280)
    _text(page, (300, 385), "เนื่องจาก")
    blank("เนื่องจาก", 360, 385, 540)

    _text(page, (40, 430), "ตั้งแต่วันที่")
    blank("ตั้งแต่วันที่", 120, 430, 260)
    _text(page, (280, 430), "ถึงวันที่")
    blank("ถึงวันที่", 340, 430, 540)

    _text(page, (40, 470), "รวม")
    blank("จำนวนวัน", 80, 470, 160, 14)
    _text(page, (165, 470), "วัน")

    _text(page, (40, 510), "ติดต่อระหว่างลา")
    blank("ติดต่อระหว่างลา", 150, 510, 540)

    _text(page, (40, 560), "สถิติการลาในปีงบประมาณนี้ (ไม่นับครั้งนี้)")
    _text(page, (40, 595), "ลาป่วยมาแล้ว")
    blank("ลาป่วยมาแล้ว", 130, 595, 200, 13)
    _text(page, (205, 595), "วัน")
    _text(page, (250, 595), "ลากิจมาแล้ว")
    blank("ลากิจมาแล้ว", 330, 595, 400, 13)
    _text(page, (405, 595), "วัน")
    _text(page, (40, 630), "ลาพักผ่อนมาแล้ว")
    blank("ลาพักผ่อนมาแล้ว", 150, 630, 220, 13)
    _text(page, (225, 630), "วัน")

    _text(page, (70, 680), "จึงเรียนมาเพื่อโปรดพิจารณา")
    _text(page, (340, 720), "ลงชื่อผู้ลา")
    blank("ผู้ลา", 340, 760, 520)
    _text(page, (40, 810), "ทดลองบนเว็บ FormDD — ข้อมูลอยู่ในเครื่องคุณ", 9, (0.45, 0.45, 0.45))

    doc.save(path)
    doc.close()
    return path, fields


def raster(pdf: Path, stem: str) -> int:
    with fitz.open(pdf) as d:
        for i, page in enumerate(d):
            pix = page.get_pixmap(matrix=fitz.Matrix(ZOOM, ZOOM))
            dest = PAGES / f"{stem}-{i}.png"
            pix.save(str(dest))
        return len(d)


def main() -> int:
    for p in (PAGES, FORMS, TPL_DIR):
        p.mkdir(parents=True, exist_ok=True)

    demo_pdf, demo_fields = make_demo()
    leave_pdf, leave_fields = make_leave()
    demo_pages = raster(demo_pdf, "demo-form")
    leave_pages = raster(leave_pdf, "leave")

    (TPL_DIR / "demo-ใบเบิก.json").write_text(
        json.dumps({"doc": "demo-form.pdf", "fields": demo_fields}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (TPL_DIR / "ใบลา.json").write_text(
        json.dumps({"doc": "ใบลา.pdf", "fields": leave_fields}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    catalog = {
        "zoom": ZOOM,
        "default_doc": "ใบลา.pdf",
        "docs": [
            {
                "id": "ใบลา.pdf",
                "pages": leave_pages,
                "page_prefix": "leave",
                "template": "ใบลา",
            },
            {
                "id": "demo-form.pdf",
                "pages": demo_pages,
                "page_prefix": "demo-form",
                "template": "demo-ใบเบิก",
            },
        ],
    }
    (OUT / "data" / "catalog.json").write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("wrote", demo_pdf, leave_pdf, "pages", demo_pages, leave_pages)
    return 0


if __name__ == "__main__":
    sys.exit(main())
