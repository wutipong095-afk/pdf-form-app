"""พรีวิวต้องวางข้อความด้วยสูตรเดียวกับ insert_htmlbox ตอนพิมพ์"""
from __future__ import annotations

import html
from pathlib import Path

import fitz
import pytest

FONT = Path(__file__).resolve().parents[1] / "fonts" / "THSarabun.ttf"


@pytest.mark.skipif(not FONT.is_file(), reason="THSarabun.ttf not in fonts/")
def test_printed_line_top_matches_preview_ascender_formula():
    font = fitz.Font(fontfile=str(FONT))
    asc, desc = float(font.ascender), float(font.descender)
    size = 14.0
    x, y = 100.0, 200.0
    text = "หน่วยงานทดสอบ"
    preview_top = y - asc * size

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    line_h = asc - desc
    top = preview_top
    rect = fitz.Rect(x, top, x + 10000, top + size * line_h + 2)
    css = (
        '@font-face {font-family: thf; src: url("%s");} '
        "body {margin: 0; padding: 0;} "
        "p {font-family: thf; font-size: %gpx; margin: 0; padding: 0; "
        "line-height: %g; white-space: pre;}" % (FONT.name, size, line_h)
    )
    page.insert_htmlbox(
        rect,
        "<p>%s</p>" % html.escape(text),
        css=css,
        archive=fitz.Archive(str(FONT.parent)),
    )
    boxes = []
    for block in page.get_text("rawdict")["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block["lines"]:
            boxes.append(line["bbox"])
    assert boxes, "htmlbox produced no text"
    printed_top = boxes[0][1]
    assert printed_top == pytest.approx(preview_top, abs=0.05)
    printed_size = boxes[0][3] - boxes[0][1]
    assert printed_size == pytest.approx(size * line_h, abs=0.05)
