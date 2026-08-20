"""ไฟล์ .formdd — ฟอร์แมตส่งออก/นำเข้า และตัวอ่านไฟล์รุ่นก่อน"""
from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

import fitz
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from job_core import (  # noqa: E402
    JOB_EXT,
    JobError,
    build_payload,
    job_filename,
    read_job,
    read_job_pdf_bytes,
    write_job,
)


def pdf_bytes() -> bytes:
    doc = fitz.open()
    doc.new_page()
    raw = doc.tobytes()
    doc.close()
    return raw


def sample_fields():
    return [
        {"name": "หน่วยงาน", "page": 0, "x": 10, "y": 20, "size": 14, "value": "โรงเรียนวัดตัวอย่าง"},
        {"name": "  ", "page": 0, "x": 1, "y": 1, "size": 12, "value": "ข้าม"},
    ]


def make(path: Path) -> Path:
    write_job(path, pdf_bytes(), build_payload(
        title="ใบลา", source_doc="demo-leave.pdf", template_name="demo-ใบลา",
        fields=sample_fields(),
    ))
    return path


def test_round_trip_keeps_thai_values(tmp_path: Path):
    path = make(tmp_path / ("a" + JOB_EXT))
    got = read_job(path)
    assert got["title"] == "ใบลา"
    assert got["source_doc"] == "demo-leave.pdf"
    assert len(got["fields"]) == 1
    assert got["fields"][0]["value"] == "โรงเรียนวัดตัวอย่าง"
    assert read_job_pdf_bytes(path).startswith(b"%PDF-")


def test_packed_pdf_is_stored_not_deflated(tmp_path: Path):
    path = make(tmp_path / ("b" + JOB_EXT))
    with zipfile.ZipFile(path) as zf:
        assert zf.getinfo("form.pdf").compress_type == zipfile.ZIP_STORED
        assert zf.getinfo("job.json").compress_type == zipfile.ZIP_DEFLATED


def test_file_names_are_sanitised():
    assert job_filename("ใบลา" + JOB_EXT) == "ใบลา" + JOB_EXT
    assert "/" not in job_filename("../../evil")
    assert ".." not in job_filename("../../evil")
    with pytest.raises(JobError, match="invalid job file name"):
        job_filename("")


def test_corrupt_zip_is_job_error_not_raw_zip_error(tmp_path: Path):
    path = tmp_path / ("broken" + JOB_EXT)
    path.write_bytes(b"not a zip at all")
    for call in (read_job, read_job_pdf_bytes):
        with pytest.raises(JobError, match="could not read job file"):
            call(path)


def test_incomplete_and_foreign_archives_rejected(tmp_path: Path):
    only_pdf = tmp_path / ("c" + JOB_EXT)
    with zipfile.ZipFile(only_pdf, "w") as zf:
        zf.writestr("form.pdf", pdf_bytes())
    with pytest.raises(JobError, match="incomplete"):
        read_job(only_pdf)

    extra = tmp_path / ("d" + JOB_EXT)
    with zipfile.ZipFile(extra, "w") as zf:
        zf.writestr("form.pdf", pdf_bytes())
        zf.writestr("job.json", json.dumps({"kind": "formdd-job", "fields": []}))
        zf.writestr("payload.exe", b"MZ")
    with pytest.raises(JobError, match="unexpected members"):
        read_job(extra)


def test_declared_size_checked_before_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    path = make(tmp_path / ("e" + JOB_EXT))
    monkeypatch.setattr("job_core.MAX_PDF_BYTES", 10)
    with pytest.raises(JobError, match="too large"):
        read_job_pdf_bytes(path)
    with pytest.raises(JobError, match="too large"):
        read_job(path)


def test_writing_a_non_pdf_is_rejected(tmp_path: Path):
    with pytest.raises(JobError, match="not a PDF"):
        write_job(tmp_path / ("f" + JOB_EXT), b"nope", build_payload(
            title="x", source_doc="", template_name="", fields=[],
        ))
    assert not list(tmp_path.glob("*" + JOB_EXT))


def test_legacy_fromdd_name_and_kind_still_open(tmp_path: Path):
    """ไฟล์ที่เซฟไว้ก่อนเปลี่ยนชื่อโปรแกรมต้องยังเปิดได้ ไม่ใช่ error"""
    assert job_filename("ใบลา.fromdd") == "ใบลา" + JOB_EXT

    path = make(tmp_path / "old.fromdd")
    with zipfile.ZipFile(path) as zf:
        parts = {n: zf.read(n) for n in zf.namelist()}
    meta = json.loads(parts["job.json"].decode("utf-8"))
    meta["kind"] = "fromdd-job"
    parts["job.json"] = json.dumps(meta, ensure_ascii=False).encode("utf-8")
    with zipfile.ZipFile(path, "w") as zf:
        for name, raw in parts.items():
            zf.writestr(name, raw)

    got = read_job(path)
    assert got["title"] == "ใบลา"
    assert read_job_pdf_bytes(path).startswith(b"%PDF-")
