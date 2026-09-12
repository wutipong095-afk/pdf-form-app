"""Bundled trial PDFs remain usable without unlocking unrelated files."""
import json
import sys
from pathlib import Path

import pytest
import pypdfium2 as pdfium

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import license_core as licensing


def test_all_trial_pdfs_are_shipped():
    assert licensing.TRIAL_DOC_NAMES == (
        "demo-form.pdf",
        "demo-leave.pdf",
        "demo-request.pdf",
        "house-lease-download.pdf",
        "bun1.pdf",
        "travel2.pdf",
    )
    for name in licensing.TRIAL_DOC_NAMES:
        assert (licensing.TRIAL_DIR / name).is_file(), name


@pytest.mark.parametrize("name,pages", [
    ("house-lease-download", 2), ("bun1", 1), ("travel2", 5),
])
def test_bundled_trial_form(name, pages, tmp_path, monkeypatch):
    monkeypatch.setattr(licensing, "license_status", lambda _: {
        "licensed": False, "machine_id": "A1B2C3D4E5F60718",
    })
    filename = name + ".pdf"
    source = licensing.TRIAL_DIR / filename
    assert filename in licensing.TRIAL_DOC_NAMES
    with pdfium.PdfDocument(str(source)) as pdf:
        assert len(pdf) == pages
    template = json.loads((licensing.TRIAL_DIR.parent / "templates_json" / (name + ".json")).read_text())
    assert template == {"doc": filename, "fields": []}
    copied = tmp_path / filename
    copied.write_bytes(source.read_bytes())
    assert licensing.can_open_document(tmp_path, filename, copied)[0]
    assert licensing.can_fill_document(tmp_path, filename, copied)[0]
    copied.write_bytes(source.read_bytes() + b"\n% changed\n")
    assert not licensing.can_open_document(tmp_path, filename, copied)[0]
    assert not licensing.can_fill_document(tmp_path, filename, copied)[0]
    assert not licensing.can_fill_document(tmp_path, "other.pdf", copied)[0]
