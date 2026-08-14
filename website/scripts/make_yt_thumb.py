"""สร้างภาพปกคลิป YouTube 16:9"""
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[2]
FONT = Path(r"C:\Windows\Fonts\LeelawUI.ttf")
OUT = ROOT / "website" / "pages" / "yt-thumb.png"
LEAVE = ROOT / "website" / "forms" / "leave.pdf"


def main() -> None:
    doc = fitz.open()
    page = doc.new_page(width=1280, height=720)
    page.draw_rect(page.rect, color=(0.06, 0.07, 0.10), fill=(0.06, 0.07, 0.10))
    page.draw_rect(fitz.Rect(0, 0, 1280, 8), color=(1, 0, 0), fill=(1, 0, 0))
    src = fitz.open(LEAVE)
    page.show_pdf_page(fitz.Rect(70, 50, 520, 670), src, 0)
    css = (
        f'@font-face {{font-family: th; src: url("{FONT.as_posix()}");}} '
        "body {font-family: th; margin:0; color:#fff;} "
        "p {margin:0 0 14px 0;}"
    )
    html = (
        '<p style="font-size:40px">สอนใช้</p>'
        '<p style="font-size:34px;color:#ffb84d">PDF Form Marker</p>'
        '<p style="font-size:22px;color:#cccccc">FromDD ใน 3 นาที</p>'
        '<p style="font-size:16px;color:#999999">มาร์คจุด · กรอกแชท · สร้าง PDF</p>'
    )
    page.insert_htmlbox(fitz.Rect(560, 180, 1220, 560), html, css=css)
    pix = page.get_pixmap()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    pix.save(str(OUT))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
