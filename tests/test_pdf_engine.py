import io
from pathlib import Path

import fitz  # Independent legacy renderer, test-only dependency.
import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.generic import RectangleObject

from reportlab.pdfgen.canvas import Canvas

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


def test_owner_locked_pdf_with_empty_user_password_is_readable():
    writer = PdfWriter()
    writer.add_blank_page(200, 300)
    writer.encrypt(user_password="", owner_password="owner-lock")
    stream = io.BytesIO()
    writer.write(stream)
    source = stream.getvalue()
    assert pdf_engine.page_sizes(source) == [{"w": 200.0, "h": 300.0}]
    data, used, orphan = pdf_engine.fill_pdf(source, [
        {"page": 0, "x": 10, "y": 40, "size": 14, "value": "เปิดได้"},
    ], FONT)
    assert (used, orphan) == (1, 0)
    assert "เปิดได้" in PdfReader(io.BytesIO(data)).pages[0].extract_text()


def test_invalid_preview_page_rejected():
    with pytest.raises(ValueError, match="Invalid page"):
        pdf_engine.render_png(Path(FONT).parents[1] / "demo/uploads/demo-form.pdf", 999)


def test_font_name_does_not_read_the_font_file(monkeypatch):
    def fail_read(self):
        raise AssertionError("font file should not be hashed")

    monkeypatch.setattr(Path, "read_bytes", fail_read)
    pdf_engine._FONT_NAMES.clear()
    first = pdf_engine._font_name(FONT)
    second = pdf_engine._font_name(FONT)
    assert first == second
    assert first.startswith("FormDD_")


def test_fill_keeps_other_fields_when_one_line_cannot_shape(monkeypatch):
    original = Canvas.drawString

    def draw(self, x, y, text, mode=None, charSpace=0, direction=None, wordSpace=None, shaping=False):
        if shaping and text == "พัง":
            raise RuntimeError("shaping failed")
        return original(self, x, y, text, mode=mode, charSpace=charSpace, direction=direction, wordSpace=wordSpace, shaping=shaping)

    monkeypatch.setattr(Canvas, "drawString", draw)
    writer = PdfWriter()
    writer.add_blank_page(400, 500)
    source = io.BytesIO()
    writer.write(source)
    data, used, orphan = pdf_engine.fill_pdf(source.getvalue(), [
        {"page": 0, "x": 20, "y": 80, "size": 14, "value": "พัง"},
        {"page": 0, "x": 20, "y": 120, "size": 14, "value": "ยังอยู่"},
    ], FONT)
    assert (used, orphan) == (2, 0)
    text = PdfReader(io.BytesIO(data)).pages[0].extract_text()
    assert "ยังอยู่" in text
    assert "พัง" in text
