"""คลังสแนปช็อตฟอร์ม — เก็บ PDF ตาม sha ไม่ซ้ำ และเก็บกวาดที่ไม่มีใครอ้าง"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import fitz
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import form_store  # noqa: E402
from fields_core import FormDataError  # noqa: E402


def pdf_bytes(pages: int = 1) -> bytes:
    doc = fitz.open()
    for _ in range(pages):
        doc.new_page()
    raw = doc.tobytes()
    doc.close()
    return raw


def test_same_pdf_is_stored_once(tmp_path: Path):
    raw = pdf_bytes()
    a = form_store.store_pdf(tmp_path, raw, source_doc="ใบลา.pdf", display_name="ใบลา.pdf")
    b = form_store.store_pdf(tmp_path, raw, source_doc="อีกที่.pdf", display_name="อีกที่.pdf")
    assert a == b == hashlib.sha256(raw).hexdigest()
    assert len(list(tmp_path.glob("*.pdf"))) == 1
    # meta ของครั้งแรกไม่ถูกเขียนทับ
    assert form_store.read_meta(tmp_path, a)["display_name"] == "ใบลา.pdf"


def test_different_pdfs_get_separate_snapshots(tmp_path: Path):
    a = form_store.store_pdf(tmp_path, pdf_bytes(1))
    b = form_store.store_pdf(tmp_path, pdf_bytes(3))
    assert a != b
    assert len(list(tmp_path.glob("*.pdf"))) == 2


def test_doc_id_round_trip():
    sha = hashlib.sha256(b"x").hexdigest()
    assert form_store.form_sha_from_doc(form_store.make_form_doc(sha)) == sha
    assert form_store.is_form_doc("@form." + sha)
    assert not form_store.is_form_doc("ใบลา.pdf")


def test_bad_sha_is_rejected():
    for bad in ("", "../../etc/passwd", "ZZZ", "a" * 63, "@form.x"):
        with pytest.raises(FormDataError, match="invalid form snapshot id"):
            form_store.form_sha_from_doc(bad)


def test_non_pdf_and_oversize_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    with pytest.raises(FormDataError, match="not a PDF"):
        form_store.store_pdf(tmp_path, b"PK\x03\x04 not a pdf")
    monkeypatch.setattr(form_store, "MAX_PDF_BYTES", 10)
    with pytest.raises(FormDataError, match="too large"):
        form_store.store_pdf(tmp_path, pdf_bytes())


def test_require_pdf_reports_missing(tmp_path: Path):
    sha = hashlib.sha256(b"nope").hexdigest()
    with pytest.raises(FileNotFoundError):
        form_store.require_pdf(tmp_path, sha)


def test_collect_garbage_keeps_referenced(tmp_path: Path):
    keep = form_store.store_pdf(tmp_path, pdf_bytes(1))
    drop = form_store.store_pdf(tmp_path, pdf_bytes(4))
    removed = form_store.collect_garbage(tmp_path, {keep})
    assert removed == [drop]
    assert form_store.pdf_path(tmp_path, keep).is_file()
    assert not form_store.pdf_path(tmp_path, drop).exists()
    assert not form_store.meta_path(tmp_path, drop).exists()


def test_collect_garbage_dry_run_removes_nothing(tmp_path: Path):
    sha = form_store.store_pdf(tmp_path, pdf_bytes())
    assert form_store.collect_garbage(tmp_path, set(), dry_run=True) == [sha]
    assert form_store.pdf_path(tmp_path, sha).is_file()
