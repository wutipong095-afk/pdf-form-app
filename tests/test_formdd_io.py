"""สะพาน .formdd ↔ ใบงาน — นำเข้า ส่งออก และย้ายข้อมูลรุ่นก่อน"""
from __future__ import annotations

import sys
from pathlib import Path

import fitz
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import form_store  # noqa: E402
import formdd_io  # noqa: E402
import job_core  # noqa: E402
import sheet_core  # noqa: E402


def pdf_bytes(pages: int = 1) -> bytes:
    doc = fitz.open()
    for _ in range(pages):
        doc.new_page()
    raw = doc.tobytes()
    doc.close()
    return raw


def write_formdd(path: Path, *, title="ใบลา", pages=1, value="โรงเรียนวัดตัวอย่าง") -> Path:
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
    src = write_formdd(tmp_path / ("x" + job_core.JOB_EXT))
    body = formdd_io.import_formdd(sheets, forms, src)
    # ฐานของชื่อคือชื่อฟอร์ม (template_name) แล้วต่อด้วยค่าแรกที่กรอก
    assert body["title"] == "demo-ใบลา — โรงเรียนวัดตัวอย่าง"
    assert body["fields"][0]["value"] == "โรงเรียนวัดตัวอย่าง"
    assert form_store.pdf_path(forms, body["form_sha"]).is_file()
    assert (sheets / body["name"]).is_file()


def test_export_round_trips_back(dirs, tmp_path: Path):
    _, sheets, forms = dirs
    src = write_formdd(tmp_path / ("y" + job_core.JOB_EXT))
    body = formdd_io.import_formdd(sheets, forms, src)
    sheet = sheet_core.read_sheet(sheets / body["name"])

    out = formdd_io.export_formdd(tmp_path / ("out" + job_core.JOB_EXT), forms, sheet)
    again = job_core.read_job(out)
    assert again["title"] == sheet["title"]
    # ไฟล์ส่งออกต้องพาฐานของชื่อไปด้วย ไม่ใช่แค่ชื่อที่คิดแล้ว
    assert again["title_base"] == sheet["title_base"] == "demo-ใบลา"
    assert again["title_auto"] is True
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
    done = formdd_io.migrate_jobs_dir(jobs, sheets, forms)

    assert done == {"moved": 5, "failed": 0}
    assert len(list(sheets.glob("*.json"))) == 5
    # ฟอร์มเดียวกันทั้ง 5 ใบ — สแนปช็อตต้องมีชุดเดียว
    assert len(list(forms.glob("*.pdf"))) == 1
    assert len(sheet_core.referenced_shas(sheets)) == 1


def test_migration_skips_broken_files_and_clears_cache(dirs):
    jobs, sheets, forms = dirs
    write_formdd(jobs / ("good" + job_core.JOB_EXT))
    (jobs / ("bad" + job_core.JOB_EXT)).write_bytes(b"not a zip")
    cache = jobs / ".cache"
    cache.mkdir()
    (cache / "stale.pdf").write_bytes(b"%PDF-old")

    done = formdd_io.migrate_jobs_dir(jobs, sheets, forms)
    assert done == {"moved": 1, "failed": 1}
    assert not cache.exists()


def test_ensure_migrated_runs_once(dirs):
    jobs, sheets, forms = dirs
    write_formdd(jobs / ("once" + job_core.JOB_EXT))

    formdd_io.ensure_migrated(jobs, sheets, forms)
    formdd_io.ensure_migrated(jobs, sheets, forms)
    assert len(list(sheets.glob("*.json"))) == 1


def test_marker_lives_outside_sheets_so_restore_does_not_redo_it(dirs):
    """กู้คืนแบบแทนที่ล้าง sheets/ — หมายต้องรอด ไม่งั้นย้ายซ้ำจนใบงานซ้ำ"""
    jobs, sheets, forms = dirs
    write_formdd(jobs / ("keep" + job_core.JOB_EXT))
    formdd_io.ensure_migrated(jobs, sheets, forms)

    for p in sheets.rglob("*"):
        if p.is_file():
            p.unlink()
    formdd_io.ensure_migrated(jobs, sheets, forms)
    assert len(list(sheets.glob("*.json"))) == 0


def test_import_leaves_no_empty_sheet_when_save_fails(dirs, tmp_path, monkeypatch):
    _, sheets, forms = dirs
    src = write_formdd(tmp_path / ("z" + job_core.JOB_EXT))

    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(formdd_io.sheet_core, "save_sheet", boom)
    with pytest.raises(OSError):
        formdd_io.import_formdd(sheets, forms, src)
    assert not list(sheets.glob("*.json"))


def test_import_then_edit_does_not_stack_the_name(dirs, tmp_path: Path):
    """ส่งออกใส่ชื่อที่คิดแล้วลงไฟล์ — นำเข้าต้องไม่เอาไปเป็นฐานจนต่อซ้อนกัน"""
    _, sheets, forms = dirs
    src = write_formdd(tmp_path / ("n" + job_core.JOB_EXT), value="โรงเรียนวัดตัวอย่าง")
    first = formdd_io.import_formdd(sheets, forms, src)
    sheet = sheets / first["name"]

    exported = formdd_io.export_formdd(
        tmp_path / ("round" + job_core.JOB_EXT), forms, sheet_core.read_sheet(sheet)
    )
    again = formdd_io.import_formdd(sheets, forms, exported)
    assert again["title"] == first["title"]

    # แก้ค่าแรกหลังนำเข้า — ชื่อต้องเปลี่ยนตาม ไม่ใช่ต่อท้ายเพิ่ม
    updated = sheet_core.save_sheet(sheets / again["name"], {
        "fields": [{"name": "หน่วยงาน", "page": 0, "x": 10, "y": 20, "size": 14,
                    "value": "โรงเรียนบ้านหนองแวง"}],
    })
    assert updated["title"] == "demo-ใบลา — โรงเรียนบ้านหนองแวง"
    assert updated["title"].count("—") == 1
    assert "โรงเรียนวัดตัวอย่าง" not in updated["title"]


def test_export_import_keeps_a_manual_name(dirs, tmp_path: Path):
    _, sheets, forms = dirs
    src = write_formdd(tmp_path / ("m" + job_core.JOB_EXT))
    body = formdd_io.import_formdd(sheets, forms, src)
    path = sheets / body["name"]
    sheet_core.save_sheet(path, {"title": "งานด่วนของ ผอ.", "rename": True})

    out = formdd_io.export_formdd(tmp_path / ("m2" + job_core.JOB_EXT), forms,
                                  sheet_core.read_sheet(path))
    back = formdd_io.import_formdd(sheets, forms, out)
    assert back["title"] == "งานด่วนของ ผอ."

    # ตั้งชื่อเองไว้แล้ว ค่าที่กรอกเปลี่ยนก็ไม่ทับ
    after = sheet_core.save_sheet(sheets / back["name"], {
        "fields": [{"name": "หน่วยงาน", "page": 0, "x": 1, "y": 2, "size": 14, "value": "คนอื่น"}],
    })
    assert after["title"] == "งานด่วนของ ผอ."


def test_migration_picks_up_legacy_fromdd_files(dirs):
    """ไฟล์นามสกุลเดิมที่ค้างอยู่ต้องถูกย้ายด้วย ไม่ใช่ถูกมองข้าม"""
    jobs, sheets, forms = dirs
    write_formdd(jobs / ("ใหม่" + job_core.JOB_EXT))
    write_formdd(jobs / ("เก่า" + job_core.LEGACY_JOB_EXT), title="ใบลาเก่า")

    done = formdd_io.migrate_jobs_dir(jobs, sheets, forms)

    assert done == {"moved": 2, "failed": 0}
    assert len(list(sheets.glob("*.json"))) == 2


def test_legacy_marker_stops_a_second_migration(dirs):
    """เครื่องที่ย้ายข้อมูลไปแล้วก่อนเปลี่ยนชื่อ ต้องไม่ถูกย้ายซ้ำจนได้ใบงานซ้ำ"""
    jobs, sheets, forms = dirs
    write_formdd(jobs / ("เก่า" + job_core.LEGACY_JOB_EXT))
    (jobs.parent / formdd_io.LEGACY_MIGRATED_MARKER).write_text("", encoding="utf-8")

    formdd_io.ensure_migrated(jobs, sheets, forms)

    assert list(sheets.glob("*.json")) == []
