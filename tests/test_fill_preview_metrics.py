"""Overlay preview must use the same baseline formula as pdf_engine.fill_pdf."""
from __future__ import annotations

import io
from pathlib import Path

import fitz  # Independent reader for glyph boxes; not the fill engine.
import pytest
from pypdf import PdfWriter

import pdf_engine

FONT = Path(__file__).resolve().parents[1] / "fonts" / "THSarabun.ttf"


@pytest.mark.skipif(not FONT.is_file(), reason="THSarabun.ttf not in fonts/")
def test_printed_line_top_matches_preview_ascender_formula():
    asc, desc = pdf_engine.font_metrics(FONT)
    size = 14.0
    x, y = 100.0, 200.0
    preview_top = y - asc * size

    writer = PdfWriter()
    writer.add_blank_page(595, 842)
    source = io.BytesIO()
    writer.write(source)
    data, used, orphan = pdf_engine.fill_pdf(
        source.getvalue(),
        [{"page": 0, "x": x, "y": y, "size": size, "value": "หน่วยงานทดสอบ"}],
        str(FONT),
    )
    assert (used, orphan) == (1, 0)

    with fitz.open(stream=data, filetype="pdf") as document:
        boxes = []
        for block in document[0].get_text("rawdict")["blocks"]:
            if block.get("type") != 0:
                continue
            for line in block["lines"]:
                boxes.append(line["bbox"])
                origin = line["spans"][0]["origin"]
        assert boxes, "fill_pdf produced no text"
        assert origin == pytest.approx((x, y), abs=0.1)
        printed_top = boxes[0][1]
        assert printed_top == pytest.approx(preview_top, abs=1.0)
        printed_size = boxes[0][3] - boxes[0][1]
        assert printed_size == pytest.approx(size * (asc - desc), abs=1.0)
