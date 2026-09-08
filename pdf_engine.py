"""PDF operations using permissively licensed engines; no PyMuPDF dependency."""
from __future__ import annotations

import hashlib
import io
import threading
from pathlib import Path

from fontTools.ttLib import TTFont as MetricsFont
from pypdf import PasswordType, PdfReader, PdfWriter
import pypdfium2 as pdfium
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

# PDFium is not thread safe; ReportLab also maintains shared font state.
_LOCK = threading.RLock()
_FONT_NAMES: dict[tuple, str] = {}
_FONT_METRICS: dict[tuple, tuple] = {}


def _reader(source):
    reader = PdfReader(io.BytesIO(source) if isinstance(source, bytes) else str(source))
    # Owner-password-only files are encrypted but open with an empty user password.
    if reader.is_encrypted and reader.decrypt("") == PasswordType.NOT_DECRYPTED:
        raise ValueError("Password-protected PDFs are not supported")
    return reader


def page_sizes(source):
    sizes = []
    for page in _reader(source).pages:
        w, h = float(page.cropbox.width), float(page.cropbox.height)
        if page.rotation % 180:
            w, h = h, w
        sizes.append({"w": w, "h": h})
    return sizes


def _font_key(fontfile):
    path = Path(fontfile)
    stat = path.stat()
    return (str(path.resolve()), stat.st_mtime_ns, stat.st_size)


def font_metrics(path):
    key = _font_key(path)
    cached = _FONT_METRICS.get(key)
    if cached is None:
        with MetricsFont(path) as font:
            units = font["head"].unitsPerEm
            cached = (font["hhea"].ascent / units, font["hhea"].descent / units)
        _FONT_METRICS[key] = cached
    return cached


def _font_name(fontfile):
    key = _font_key(fontfile)
    name = _FONT_NAMES.get(key)
    if name is None:
        name = "FormDD_" + hashlib.sha256(repr(key).encode()).hexdigest()[:16]
        _FONT_NAMES[key] = name
    return name


def render_png(source, page_number, scale=1.5):
    with _LOCK:
        with pdfium.PdfDocument(source if isinstance(source, bytes) else str(source)) as doc:
            if not 0 <= page_number < len(doc):
                raise ValueError("Invalid page")
            page = doc[page_number]
            try:
                bitmap = page.render(scale=scale)
                try:
                    output = io.BytesIO()
                    bitmap.to_pil().save(output, format="PNG")
                    return output.getvalue()
                finally:
                    bitmap.close()
            finally:
                page.close()


def _draw_line(canvas, x, y, text, shaping):
    try:
        canvas.drawString(x, y, text, shaping=shaping)
        return
    except Exception:
        if not shaping:
            return
    try:
        canvas.drawString(x, y, text, shaping=False)
    except Exception:
        return


def fill_pdf(source, fields, fontfile):
    with _LOCK:
        reader = _reader(source)
        writer = PdfWriter(clone_from=reader)
        fontname = _font_name(fontfile)
        if fontname not in pdfmetrics.getRegisteredFontNames():
            font = TTFont(fontname, str(fontfile), shapable=True)
            pdfmetrics.registerFont(font)
        else:
            font = pdfmetrics.getFont(fontname)
        shaping = bool(getattr(font, "shapable", False))
        asc, desc = font_metrics(fontfile)
        grouped = {}
        used = orphan = 0
        for field in fields:
            value = str(field.get("value") or "").strip()
            if not value:
                continue
            number = int(field["page"])
            if not 0 <= number < len(writer.pages):
                orphan += 1
                continue
            grouped.setdefault(number, []).append((field, value))
            used += 1
        for number, values in grouped.items():
            page = writer.pages[number]
            buffer = io.BytesIO()
            canvas = Canvas(buffer, pagesize=(float(page.mediabox.width), float(page.mediabox.height)))
            for field, value in values:
                size = float(field.get("size", 14))
                canvas.setFont(fontname, size)
                # Preserve legacy PyMuPDF unrotated crop-relative baseline coordinates.
                x = float(page.cropbox.left) + float(field["x"])
                y = float(page.cropbox.top) - float(field["y"])
                for line, text in enumerate(value.split("\n")):
                    _draw_line(canvas, x, y - line * size * (asc - desc), text, shaping)
            canvas.save()
            overlay = PdfReader(buffer).pages[0]
            # Do not clip overlays to a zero-origin MediaBox on offset pages.
            overlay.mediabox = page.mediabox
            overlay.cropbox = page.cropbox
            page.merge_page(overlay)
        for page in writer.pages:
            page.compress_content_streams()
        writer.compress_identical_objects()
        result = io.BytesIO()
        writer.write(result)
        return result.getvalue(), used, orphan
