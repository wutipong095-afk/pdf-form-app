"""เส้น /api/sheets + ประวัติงาน — รันด้วย DATA_DIR ชั่วคราว ไม่แตะข้อมูลจริง"""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ["AUTH_REQUIRED"] = "false"
if "pfm-tests-" not in os.environ.get("DATA_DIR", ""):
    _TEST_DATA_DIR = Path(tempfile.mkdtemp(prefix="pfm-tests-"))
    os.environ["DATA_DIR"] = str(_TEST_DATA_DIR)
    os.environ["LOG_DIR"] = str(_TEST_DATA_DIR / "logs")
else:
    _TEST_DATA_DIR = Path(os.environ["DATA_DIR"])

import app as A  # noqa: E402
import job_core  # noqa: E402

assert "pfm-tests-" in Path(A.DATA_DIR).resolve().as_posix(), (
    f"tests must not run against the real data dir (got {A.DATA_DIR})"
)


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(A, "USERS_DIR", tmp_path)
    c = A.app.test_client()
    c.get("/")
    with c.session_transaction() as s:
        c._tok = s["_csrf_token"]
    c._root = tmp_path
    return c


def hdr(c, json_body=True):
    h = {"X-CSRF-Token": c._tok}
    if json_body:
        h["Content-Type"] = "application/json"
    return h


def fields(value="โรงเรียนวัดตัวอย่าง"):
    return [{"name": "หน่วยงาน", "page": 0, "x": 114, "y": 100, "size": 14, "value": value}]


def create_sheet(c, value="โรงเรียนวัดตัวอย่าง"):
    return c.post("/api/sheets", headers=hdr(c), json={
        "source_doc": "demo-leave.pdf",
        "title": "ใบลา",
        "template_name": "demo-ใบลา",
        "fields": fields(value),
    })


def sheets_dir(c) -> Path:
    return next(p for p in c._root.rglob("sheets") if p.is_dir())


def forms_dir(c) -> Path:
    return next(p for p in c._root.rglob("forms") if p.is_dir())


def test_create_and_reload_sheet(client):
    r = create_sheet(client)
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body["doc_id"].startswith("@form.")
    assert body["source_doc"] == "demo-leave.pdf"
    # ตั้งชื่อให้หาเจอ — ต่อค่าแรกที่ไม่ว่างท้ายชื่อฟอร์ม
    assert "โรงเรียนวัดตัวอย่าง" in body["title"]

    got = client.get("/api/sheets/" + body["sheet"]).get_json()
    assert got["fields"][0]["value"] == "โรงเรียนวัดตัวอย่าง"
    assert got["form_sha"] == body["form_sha"]


def test_update_keeps_form_and_source(client):
    created = create_sheet(client).get_json()
    r = client.post("/api/sheets", headers=hdr(client), json={
        "sheet": created["sheet"],
        "fields": fields("แก้แล้ว"),
    })
    assert r.status_code == 200
    body = r.get_json()
    assert body["fields"][0]["value"] == "แก้แล้ว"
    assert body["form_sha"] == created["form_sha"]
    assert body["source_doc"] == "demo-leave.pdf"


def test_sheets_from_one_form_share_a_single_snapshot(client):
    for _ in range(4):
        assert create_sheet(client).status_code == 200
    assert len(list(sheets_dir(client).glob("*.json"))) == 4
    assert len(list(forms_dir(client).glob("*.pdf"))) == 1


def test_sheet_file_is_far_smaller_than_the_form(client):
    body = create_sheet(client).get_json()
    sheet = sheets_dir(client) / body["sheet"]
    form = next(forms_dir(client).glob("*.pdf"))
    assert sheet.stat().st_size * 4 < form.stat().st_size


def test_history_lists_sheets_with_status(client):
    created = create_sheet(client).get_json()
    st = client.get("/api/history").get_json()
    row = next(f for f in st["files"] if f.get("sheet") == created["sheet"])
    assert row["kind"] == "sheet"
    assert row["printed"] is False
    assert (row["filled"], row["pins"]) == (1, 1)


def test_fill_from_sheet_marks_it_printed(client):
    created = create_sheet(client).get_json()
    r = client.post("/api/fill", headers=hdr(client), json={
        "doc": created["doc_id"],
        "sheet": created["sheet"],
        "fields": fields(),
        "outname": "ใบลา",
    })
    assert r.status_code == 200, r.get_json()
    out = r.get_json()["file"]

    got = client.get("/api/sheets/" + created["sheet"]).get_json()
    assert got["printed"] == [out]
    st = client.get("/api/history").get_json()
    row = next(f for f in st["files"] if f.get("sheet") == created["sheet"])
    assert row["printed"] is True


def test_printed_pdf_cannot_be_filled_again(client):
    created = create_sheet(client).get_json()
    out = client.post("/api/fill", headers=hdr(client), json={
        "doc": created["doc_id"], "sheet": created["sheet"], "fields": fields(), "outname": "ใบลา",
    }).get_json()["file"]
    r = client.post("/api/fill", headers=hdr(client), json={
        "doc": "@out." + out, "fields": fields(),
    })
    assert r.status_code == 400


def test_duplicate_makes_an_independent_sheet(client):
    created = create_sheet(client).get_json()
    dup = client.post(
        "/api/sheets/" + created["sheet"] + "/duplicate", headers=hdr(client)
    ).get_json()
    assert dup["sheet"] != created["sheet"]
    assert dup["form_sha"] == created["form_sha"]
    assert dup["fields"][0]["value"] == "โรงเรียนวัดตัวอย่าง"

    client.post("/api/sheets", headers=hdr(client), json={
        "sheet": dup["sheet"], "fields": fields("ของใหม่"),
    })
    original = client.get("/api/sheets/" + created["sheet"]).get_json()
    assert original["fields"][0]["value"] == "โรงเรียนวัดตัวอย่าง"
    # ใช้ฟอร์มร่วมกัน ไม่เพิ่มสำเนา PDF
    assert len(list(forms_dir(client).glob("*.pdf"))) == 1


def test_delete_sheet_collects_the_unused_snapshot(client):
    created = create_sheet(client).get_json()
    assert len(list(forms_dir(client).glob("*.pdf"))) == 1

    r = client.delete("/api/sheets/" + created["sheet"], headers=hdr(client))
    assert r.status_code == 200
    assert r.get_json()["snapshots_freed"] == 1
    assert not list(sheets_dir(client).glob("*.json"))
    assert not list(forms_dir(client).glob("*.pdf"))


def test_delete_keeps_snapshot_another_sheet_still_uses(client):
    a = create_sheet(client).get_json()
    b = create_sheet(client).get_json()
    r = client.delete("/api/sheets/" + a["sheet"], headers=hdr(client))
    assert r.get_json()["snapshots_freed"] == 0
    assert client.get("/api/sheets/" + b["sheet"]).status_code == 200
    assert len(list(forms_dir(client).glob("*.pdf"))) == 1


def test_delete_missing_sheet_is_404(client):
    assert client.delete("/api/sheets/ไม่มีจริง.json", headers=hdr(client)).status_code == 404


def test_export_and_import_round_trip(client):
    created = create_sheet(client).get_json()
    r = client.get("/api/sheets/" + created["sheet"] + "/export")
    assert r.status_code == 200
    raw = r.get_data()
    assert zipfile.is_zipfile(io.BytesIO(raw))

    client.delete("/api/sheets/" + created["sheet"], headers=hdr(client))
    assert not list(sheets_dir(client).glob("*.json"))

    r = client.post(
        "/api/sheets/import",
        headers={"X-CSRF-Token": client._tok},
        data={"file": (io.BytesIO(raw), "ใบลา" + job_core.JOB_EXT)},
        content_type="multipart/form-data",
    )
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body["fields"][0]["value"] == "โรงเรียนวัดตัวอย่าง"
    assert body["form_sha"] == created["form_sha"]


def test_import_rejects_a_non_fromdd_file(client):
    r = client.post(
        "/api/sheets/import",
        headers={"X-CSRF-Token": client._tok},
        data={"file": (io.BytesIO(b"%PDF-nope"), "x.pdf")},
        content_type="multipart/form-data",
    )
    assert r.status_code == 400


def test_import_rejects_a_corrupt_archive(client):
    r = client.post(
        "/api/sheets/import",
        headers={"X-CSRF-Token": client._tok},
        data={"file": (io.BytesIO(b"not a zip"), "x" + job_core.JOB_EXT)},
        content_type="multipart/form-data",
    )
    assert r.status_code == 400


def test_template_save_strips_values(client):
    r = client.post("/api/template/ใบลา", headers=hdr(client), json={
        "doc": "demo-leave.pdf",
        "fields": fields("ค่าที่ไม่ควรติดไปกับเทมเพลต"),
    })
    assert r.status_code == 200, r.get_json()
    got = client.get("/api/template/ใบลา").get_json()
    assert got["fields"][0]["value"] == ""


def test_template_cannot_be_saved_from_a_snapshot(client):
    created = create_sheet(client).get_json()
    r = client.post("/api/template/x", headers=hdr(client), json={
        "doc": created["doc_id"], "fields": fields(),
    })
    assert r.status_code == 400


def test_backup_includes_sheets_and_snapshots(client):
    created = create_sheet(client).get_json()
    r = client.post("/api/backup", headers=hdr(client, json_body=False))
    assert r.status_code == 200
    with zipfile.ZipFile(io.BytesIO(r.get_data())) as zf:
        names = zf.namelist()
    assert f"user/sheets/{created['sheet']}" in names
    assert f"user/forms/{created['form_sha']}.pdf" in names


def test_sheets_need_csrf(client):
    r = client.post("/api/sheets", headers={"Content-Type": "application/json"}, json={
        "source_doc": "demo-leave.pdf", "fields": fields(),
    })
    assert r.status_code == 403
    assert client.delete("/api/sheets/x.json").status_code == 403


def test_invalid_field_geometry_is_400(client):
    r = client.post("/api/sheets", headers=hdr(client), json={
        "source_doc": "demo-leave.pdf",
        "fields": [{"name": "ก", "page": "2.0", "x": 1, "y": 1, "size": 14, "value": "ก"}],
    })
    assert r.status_code == 400
    assert r.get_json()["error"]


def test_sheet_needs_a_real_source(client):
    r = client.post("/api/sheets", headers=hdr(client), json={"fields": fields()})
    assert r.status_code == 400
    r = client.post("/api/sheets", headers=hdr(client), json={
        "source_doc": "ไม่มีไฟล์นี้.pdf", "fields": fields(),
    })
    assert r.status_code == 404


def test_corrupt_sheet_is_400_not_500(client):
    created = create_sheet(client).get_json()
    (sheets_dir(client) / created["sheet"]).write_text("{broken", encoding="utf-8")
    assert client.get("/api/sheets/" + created["sheet"]).status_code == 400
    r = client.post("/api/sheets", headers=hdr(client), json={
        "sheet": created["sheet"], "fields": fields(),
    })
    assert r.status_code == 400


def test_missing_snapshot_is_404_not_500(client):
    created = create_sheet(client).get_json()
    for p in forms_dir(client).glob("*.pdf"):
        p.unlink()
    assert client.get("/api/pageinfo/" + created["doc_id"]).status_code == 404


def test_legacy_fromdd_files_are_migrated_on_first_use(client, tmp_path):
    """ผู้ใช้รุ่นก่อนมี .fromdd อยู่ — ต้องโผล่เป็นใบงานเองโดยไม่ต้องทำอะไร"""
    user_root = next(p for p in tmp_path.iterdir() if p.is_dir())
    jobs = user_root / "jobs"
    jobs.mkdir(parents=True, exist_ok=True)
    for marker in user_root.glob(".migrated-from-fromdd"):
        marker.unlink()

    src = A._pdf_path("local", "demo-leave.pdf")
    job_core.write_job(jobs / ("เก่า" + job_core.JOB_EXT), src.read_bytes(), job_core.build_payload(
        title="ใบลาเก่า", source_doc="demo-leave.pdf", template_name="ใบลา",
        fields=fields("ของเดิม"),
    ))
    (user_root / ".migrated-from-fromdd").unlink(missing_ok=True)

    st = client.get("/api/history").get_json()
    rows = [f for f in st["files"] if f.get("kind") == "sheet"]
    assert any("ใบลาเก่า" in (f.get("title") or "") for f in rows)
    moved = next(f for f in rows if "ใบลาเก่า" in (f.get("title") or ""))
    got = client.get("/api/sheets/" + moved["sheet"]).get_json()
    assert got["fields"][0]["value"] == "ของเดิม"


def test_autosave_does_not_overwrite_the_auto_title(client):
    """ช่อง #tplname คือชื่อเทมเพลต ไม่ใช่ชื่อใบ — ออโต้เซฟต้องไม่เอาไปทับ"""
    created = create_sheet(client).get_json()
    assert created["title"] == "ใบลา — โรงเรียนวัดตัวอย่าง"

    # เลียนแบบสิ่งที่ไคลเอนต์ส่งตอนพิมพ์ต่อ
    body = client.post("/api/sheets", headers=hdr(client), json={
        "sheet": created["sheet"],
        "title": "demo-ใบลา",
        "template_name": "demo-ใบลา",
        "fields": fields("โรงเรียนบ้านหนองแวง"),
    }).get_json()
    assert body["title"] == "ใบลา — โรงเรียนบ้านหนองแวง"

    st = client.get("/api/history").get_json()
    row = next(f for f in st["files"] if f.get("sheet") == created["sheet"])
    assert "โรงเรียนบ้านหนองแวง" in row["title"]
    # ค้นด้วยชื่อหน่วยงานต้องเจอใบนั้น
    found = client.get("/api/history?q=" + "หนองแวง").get_json()
    assert any(f.get("sheet") == created["sheet"] for f in found["files"])


def test_deleting_the_open_sheet_frees_the_snapshot_it_was_showing(client):
    """ฝั่ง UI ต้องพาจอกลับไปที่ต้นฉบับ เพราะ @form.{sha} ตายไปพร้อมใบสุดท้าย"""
    created = create_sheet(client).get_json()
    assert client.get("/api/pageinfo/" + created["doc_id"]).status_code == 200

    client.delete("/api/sheets/" + created["sheet"], headers=hdr(client))
    assert client.get("/api/pageinfo/" + created["doc_id"]).status_code == 404
    # ต้นฉบับยังอยู่ — เปิดต่อได้ ใบใหม่จึงสร้างได้
    assert client.get("/api/pageinfo/demo-leave.pdf").status_code == 200
    assert client.post("/api/sheets", headers=hdr(client), json={
        "source_doc": "demo-leave.pdf", "title": "ใบลา", "fields": fields(),
    }).status_code == 200
