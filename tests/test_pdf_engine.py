import io
from pathlib import Path

import fitz  # Independent legacy renderer, test-only dependency.
import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.generic import RectangleObject

import pdf_engine

FONT = str(Path(__file__).resolve().parents[1] / "fonts/THSarabun.ttf")


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_thai_multiline_preserves_legacy_coordinates_and_page_geometry(rotation):
    writer = PdfWriter()
    page = writer.add_blank_page(600, 800)
    page.cropbox = RectangleObject([20, 30, 580, 770])
    page.rotate(rotation)
    writer.add_blank_page(400, 500)
    source = io.BytesIO()
    writer.write(source)
    data, used, orphan = pdf_engine.fill_pdf(source.getvalue(), [
        {"page": 0, "x": 100, "y": 200, "size": 20, "value": "ขี่ สี่ ปั่น น้ำ\nผู้ใหญ่"},
        {"page": 1, "x": 50, "y": 80, "size": 14, "value": "เก้าอี้"},
        {"page": 9, "x": 0, "y": 0, "value": "orphan"},
    ], FONT)
    assert (used, orphan) == (2, 1)
    result = PdfReader(io.BytesIO(data))
    assert len(result.pages) == 2
    assert result.pages[0].rotation == rotation
    assert list(result.pages[0].cropbox) == [20, 30, 580, 770]
    assert "ขี่" in result.pages[0].extract_text()
    assert "น้ำ" in result.pages[0].extract_text()
    assert "เก้าอี้" in result.pages[1].extract_text()
    with fitz.open(stream=data, filetype="pdf") as document:
        lines = document[0].get_text("dict")["blocks"][0]["lines"]
        first = lines[0]["spans"][0]
        assert first["origin"] == pytest.approx((100, 200), abs=0.1)
    assert pdf_engine.render_png(data, 0).startswith(b"\x89PNG")


def test_encrypted_pdf_rejected():
    writer = PdfWriter()
    writer.add_blank_page(100, 100)
    writer.encrypt("secret")
    stream = io.BytesIO()
    writer.write(stream)
    with pytest.raises(ValueError, match="Password"):
        pdf_engine.page_sizes(stream.getvalue())


def test_invalid_preview_page_rejected():
    with pytest.raises(ValueError, match="Invalid page"):
        pdf_engine.render_png(Path(FONT).parents[1] / "demo/uploads/demo-form.pdf", 999)


def test_font_name_is_cached_for_the_same_file(monkeypatch):
    font = Path(FONT)
    reads = {"n": 0}
    original = Path.read_bytes

    def counted(self):
        if Path(self).resolve() == font.resolve():
            reads["n"] += 1
        return original(self)

    monkeypatch.setattr(Path, "read_bytes", counted)
    pdf_engine._FONT_NAMES.clear()
    first = pdf_engine._font_name(font)
    second = pdf_engine._font_name(font)
    assert first == second
    assert reads["n"] == 1
