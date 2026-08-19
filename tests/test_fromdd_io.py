"""สะพาน .fromdd ↔ ใบงาน — นำเข้า ส่งออก และย้ายข้อมูลรุ่นก่อน"""
from __future__ import annotations

import sys
from pathlib import Path

import fitz
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import form_store  # noqa: E402
import fromdd_io  # noqa: E402
import job_core  # noqa: E402
import sheet_core  # noqa: E402


def pdf_bytes(pages: int = 1) -> bytes:
    doc = fitz.open()
    for _ in range(pages):
        doc.new_page()
    raw = doc.tobytes()
    doc.close()
    return raw


def write_fromdd(path: Path, *, title="ใบลา", pages=1, value="โรงเรียนวัดตัวอย่าง") -> Path:
    job_core.write_job(path, pdf_bytes(pages), job_core.build_payload(
        title=title, source_doc="demo-leave.pdf", template_name="demo-ใบลา",
        fields=[{"name": "หน่วยงาน", "page": 0, "x": 10, "y": 20, "size": 14, "value": value}],
    ))
    return path


@pytest.fixture()
def dirs(tmp_path: Path):
    jobs, sheets, forms = tmp_path / "jobs", tmp_path / "sheets", tmp_path / "forms"
    for d in (jobs, sheets, forms):
        d.mkdir()
    return jobs, sheets, forms


def test_import_creates_sheet_and_snapshot(dirs, tmp_path: Path):
    _, sheets, forms = dirs
    src = write_fromdd(tmp_path / ("x" + job_core.JOB_EXT))
    body = fromdd_io.import_fromdd(sheets, forms, src)
    assert body["title"] == "ใบลา"
    assert body["fields"][0]["value"] == "โรงเรียนวัดตัวอย่าง"
    assert form_store.pdf_path(forms, body["form_sha"]).is_file()
    assert (sheets / body["name"]).is_file()


def test_export_round_trips_back(dirs, tmp_path: Path):
    _, sheets, forms = dirs
    src = write_fromdd(tmp_path / ("y" + job_core.JOB_EXT))
    body = fromdd_io.import_fromdd(sheets, forms, src)
    sheet = sheet_core.read_sheet(sheets / body["name"])

    out = fromdd_io.export_fromdd(tmp_path / ("out" + job_core.JOB_EXT), forms, sheet)
    again = job_core.read_job(out)
    assert again["title"] == "ใบลา"
    assert again["source_doc"] == "demo-leave.pdf"
    assert again["fields"][0]["value"] == "โรงเรียนวัดตัวอย่าง"
    assert job_core.read_job_pdf_bytes(out).startswith(b"%PDF-")


def test_migration_dedupes_the_same_form(dirs):
    jobs, sheets, forms = dirs
    raw = pdf_bytes()
    for i in range(5):
        job_core.write_job(jobs / f"job{i}{job_core.JOB_EXT}", raw, job_core.build_payload(
            title=f"ใบเบิก {i}", source_doc="req.pdf", template_name="ใบเบิก",
            fields=[{"name": "ก", "page": 0, "x": 1, "y": 2, "size": 14, "value": str(i)}],
        ))
    done = fromdd_io.migrate_jobs_dir(jobs, sheets, forms)

    assert done == {"moved": 5, "failed": 0}
    assert len(list(sheets.glob("*.json"))) == 5
    # ฟอร์มเดียวกันทั้ง 5 ใบ — สแนปช็อตต้องมีชุดเดียว
    assert len(list(forms.glob("*.pdf"))) == 1
    assert len(sheet_core.referenced_shas(sheets)) == 1


def test_migration_skips_broken_files_and_clears_cache(dirs):
    jobs, sheets, forms = dirs
    write_fromdd(jobs / ("good" + job_core.JOB_EXT))
    (jobs / ("bad" + job_core.JOB_EXT)).write_bytes(b"not a zip")
    cache = jobs / ".cache"
    cache.mkdir()
    (cache / "stale.pdf").write_bytes(b"%PDF-old")

    done = fromdd_io.migrate_jobs_dir(jobs, sheets, forms)
    assert done == {"moved": 1, "failed": 1}
    assert not cache.exists()


def test_ensure_migrated_runs_once(dirs):
    jobs, sheets, forms = dirs
    write_fromdd(jobs / ("once" + job_core.JOB_EXT))

    fromdd_io.ensure_migrated(jobs, sheets, forms)
    fromdd_io.ensure_migrated(jobs, sheets, forms)
    assert len(list(sheets.glob("*.json"))) == 1


def test_marker_lives_outside_sheets_so_restore_does_not_redo_it(dirs):
    """กู้คืนแบบแทนที่ล้าง sheets/ — หมายต้องรอด ไม่งั้นย้ายซ้ำจนใบงานซ้ำ"""
    jobs, sheets, forms = dirs
    write_fromdd(jobs / ("keep" + job_core.JOB_EXT))
    fromdd_io.ensure_migrated(jobs, sheets, forms)

    for p in sheets.rglob("*"):
        if p.is_file():
            p.unlink()
    fromdd_io.ensure_migrated(jobs, sheets, forms)
    assert len(list(sheets.glob("*.json"))) == 0


def test_import_leaves_no_empty_sheet_when_save_fails(dirs, tmp_path, monkeypatch):
    _, sheets, forms = dirs
    src = write_fromdd(tmp_path / ("z" + job_core.JOB_EXT))

    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(fromdd_io.sheet_core, "save_sheet", boom)
    with pytest.raises(OSError):
        fromdd_io.import_fromdd(sheets, forms, src)
    assert not list(sheets.glob("*.json"))
