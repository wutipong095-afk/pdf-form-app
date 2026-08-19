"""ไฟล์งาน .fromdd — แพ็ก PDF ว่าง + ค่า เปิดแก้ต่อได้"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import fitz
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from job_core import (  # noqa: E402
    JOB_EXT,
    JobError,
    extract_job_pdf,
    is_job_doc,
    job_filename_from_doc,
    layout_fields,
    list_jobs,
    make_job_doc,
    normalize_fields,
    read_job,
    read_job_pdf_bytes,
    save_job,
    unique_job_name,
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


def test_round_trip_keeps_thai_values(tmp_path: Path):
    path = tmp_path / "ใบลา-20260819-153000.fromdd"
    payload = save_job(
        path,
        {
            "title": "ใบลา",
            "source_doc": "demo-leave.pdf",
            "template_name": "demo-ใบลา",
            "fields": sample_fields(),
        },
        pdf_bytes=pdf_bytes(),
    )
    assert path.is_file()
    again = read_job(path)
    assert again["kind"] == "fromdd-job"
    assert again["title"] == "ใบลา"
    assert again["fields"] == payload["fields"]
    assert again["fields"][0]["value"] == "โรงเรียนวัดตัวอย่าง"
    assert len(again["fields"]) == 1


def test_update_keeps_packed_pdf(tmp_path: Path):
    path = tmp_path / "job.fromdd"
    original = pdf_bytes()
    save_job(path, {"title": "ก", "source_doc": "a.pdf", "fields": sample_fields()}, pdf_bytes=original)
    save_job(path, {"title": "ก", "fields": [{"name": "หน่วยงาน", "page": 0, "x": 1, "y": 2, "size": 14, "value": "ใหม่"}]})
    again = read_job(path)
    assert again["source_doc"] == "a.pdf"
    assert again["fields"][0]["value"] == "ใหม่"
    cache = extract_job_pdf(path)
    assert cache.read_bytes().startswith(b"%PDF-")


def test_unique_names_do_not_collide(tmp_path: Path):
    a = unique_job_name(tmp_path, "ใบลา", now=1_700_000_000)
    b = unique_job_name(tmp_path, "ใบลา", now=1_700_000_000)
    assert a.endswith(JOB_EXT)
    assert a != b


def test_job_doc_ids_round_trip():
    name = "ใบลา-20260819-153000.fromdd"
    doc = make_job_doc(name)
    assert is_job_doc(doc)
    assert job_filename_from_doc(doc) == name


def test_layout_fields_strip_values():
    out = layout_fields(sample_fields())
    assert out[0]["name"] == "หน่วยงาน"
    assert out[0]["value"] == ""


def test_list_jobs_skips_cache_and_matches_query(tmp_path: Path):
    save_job(
        tmp_path / "ใบลา-20260819-153000.fromdd",
        {"title": "ใบลา", "source_doc": "demo-leave.pdf", "fields": sample_fields()},
        pdf_bytes=pdf_bytes(),
    )
    (tmp_path / ".cache").mkdir()
    (tmp_path / ".cache" / "ใบลา-20260819-153000.pdf").write_bytes(b"%PDF-1.4")
    listed = list_jobs(tmp_path)
    assert len(listed) == 1
    assert listed[0]["kind"] == "job"
    assert listed[0]["group"] == "ใบลา"
    assert list_jobs(tmp_path, "ลา")
    assert list_jobs(tmp_path, "ไม่มี") == []


def test_bad_zip_is_rejected(tmp_path: Path):
    path = tmp_path / "bad.fromdd"
    path.write_bytes(b"not a zip")
    with pytest.raises(JobError):
        read_job(path)


def test_extra_zip_members_rejected(tmp_path: Path):
    path = tmp_path / "extra.fromdd"
    import zipfile

    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("form.pdf", pdf_bytes())
        zf.writestr("job.json", json.dumps({"kind": "fromdd-job", "fields": []}))
        zf.writestr("secret.txt", "nope")
    with pytest.raises(JobError):
        read_job(path)


def test_save_without_pdf_on_missing_file_fails(tmp_path: Path):
    with pytest.raises(JobError):
        save_job(tmp_path / "missing.fromdd", {"title": "ก", "fields": []})


def test_bad_field_geometry_is_job_error():
    with pytest.raises(JobError, match="invalid field geometry"):
        normalize_fields([{"name": "a", "page": "2.0"}])
    with pytest.raises(JobError, match="invalid field geometry"):
        normalize_fields([{"name": "a", "x": "abc"}])


def test_packed_pdf_is_stored_not_deflated(tmp_path: Path):
    import zipfile

    path = tmp_path / "stored.fromdd"
    save_job(
        path,
        {"title": "ก", "source_doc": "a.pdf", "fields": sample_fields()},
        pdf_bytes=pdf_bytes(),
    )
    with zipfile.ZipFile(path) as zf:
        assert zf.getinfo("form.pdf").compress_type == zipfile.ZIP_STORED
        assert zf.getinfo("job.json").compress_type == zipfile.ZIP_DEFLATED


def test_read_pdf_checks_declared_size_before_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    path = tmp_path / "big.fromdd"
    save_job(
        path,
        {"title": "ก", "source_doc": "a.pdf", "fields": sample_fields()},
        pdf_bytes=pdf_bytes(),
    )
    monkeypatch.setattr("job_core.MAX_PDF_BYTES", 10)
    with pytest.raises(JobError, match="too large"):
        read_job_pdf_bytes(path)


def test_extract_reuses_cache_after_json_only_save(tmp_path: Path):
    path = tmp_path / "cache.fromdd"
    save_job(
        path,
        {"title": "ก", "source_doc": "a.pdf", "fields": sample_fields()},
        pdf_bytes=pdf_bytes(),
    )
    first = extract_job_pdf(path)
    mtime = first.stat().st_mtime
    save_job(path, {"title": "ก", "fields": [{"name": "หน่วยงาน", "page": 0, "x": 1, "y": 2, "size": 14, "value": "ใหม่"}]})
    again = extract_job_pdf(path)
    assert again == first
    assert again.stat().st_mtime == mtime


def test_non_finite_and_out_of_range_geometry_rejected():
    for bad in ({"x": "nan"}, {"y": "inf"}, {"size": "1e400"}, {"x": 1e12}):
        item = {"name": "a", "page": 0, "x": 1, "y": 1, "size": 14, **bad}
        with pytest.raises(JobError, match="invalid field geometry"):
            normalize_fields([item])
    with pytest.raises(JobError, match="invalid field geometry"):
        normalize_fields([{"name": "a", "page": -1}])
    with pytest.raises(JobError, match="invalid field geometry"):
        normalize_fields([{"name": "a", "page": 10**20}])
