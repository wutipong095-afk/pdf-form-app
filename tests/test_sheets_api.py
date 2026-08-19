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
    # รุ่นก่อนเก็บ title กับ template_name จากช่องเดียวกัน จึงเท่ากันเสมอ
    job_core.write_job(jobs / ("เก่า" + job_core.JOB_EXT), src.read_bytes(), job_core.build_payload(
        title="ใบลาเก่า", source_doc="demo-leave.pdf", template_name="ใบลาเก่า",
        fields=fields("ของเดิม"),
    ))
    (user_root / ".migrated-from-fromdd").unlink(missing_ok=True)

    st = client.get("/api/history").get_json()
    rows = [f for f in st["files"] if f.get("kind") == "sheet"]
    moved = next(f for f in rows if "ใบลาเก่า" in (f.get("title") or ""))
    # ไฟล์รุ่นก่อนไม่มี title_base — ต้องได้ชื่อที่ค้นเจอจากค่าที่กรอก ไม่ใช่ชื่อฟอร์มเปล่า ๆ
    assert moved["title"] == "ใบลาเก่า — ของเดิม"
    got = client.get("/api/sheets/" + moved["sheet"]).get_json()
    assert got["fields"][0]["value"] == "ของเดิม"

    # แก้ค่าต่อหลังย้ายแล้ว ชื่อต้องเปลี่ยนตาม ไม่ต่อซ้อน
    after = client.post("/api/sheets", headers=hdr(client), json={
        "sheet": moved["sheet"], "template_name": "ใบลาเก่า", "fields": fields("ของใหม่"),
    }).get_json()
    assert after["title"] == "ใบลาเก่า — ของใหม่"


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


def make_pdf(pages: int = 1) -> bytes:
    import fitz

    doc = fitz.open()
    for _ in range(pages):
        doc.new_page()
    raw = doc.tobytes()
    doc.close()
    return raw


@pytest.fixture()
def licensed(monkeypatch):
    """แพ็กทดลองถูกล็อกด้วยเนื้อไฟล์ — เคสฟอร์มเปลี่ยนเวอร์ชันต้องทดสอบกับเอกสารจริง"""
    monkeypatch.setenv("LICENSE_BYPASS", "1")


def upload(client, name: str, pages: int = 1) -> str:
    r = client.post(
        "/api/upload",
        headers={"X-CSRF-Token": client._tok},
        data={"file": (io.BytesIO(make_pdf(pages)), name)},
        content_type="multipart/form-data",
    )
    assert r.status_code == 200, r.get_json()
    return r.get_json()["name"]


def sheet_from(client, doc: str, value: str = "โรงเรียนวัดตัวอย่าง") -> dict:
    r = client.post("/api/sheets", headers=hdr(client), json={
        "source_doc": doc, "title": "ใบเบิก", "template_name": "ใบเบิก", "fields": fields(value),
    })
    assert r.status_code == 200, r.get_json()
    return r.get_json()


def replace_upload(client, name: str, pages: int = 3) -> None:
    """อัปโหลดฟอร์มชื่อเดิมทับด้วยไฟล์คนละตัว — สิ่งที่เกิดจริงตอนฟอร์มออกเวอร์ชันใหม่"""
    upload(client, name, pages=pages)


def test_sheet_reports_which_form_it_came_from(client):
    created = create_sheet(client).get_json()
    assert created["source_name"] == "demo-leave.pdf"
    assert created["source_present"] is True
    assert created["source_changed"] is False

    row = next(
        f for f in client.get("/api/history").get_json()["files"]
        if f.get("sheet") == created["sheet"]
    )
    assert row["source_name"] == "demo-leave.pdf"
    assert row["source_changed"] is False


def test_replacing_the_form_does_not_change_old_sheets(client, licensed):
    """แกนของการตัดสินใจ: อัปโหลดทับแล้วงานเก่าต้องยังพิมพ์ออกมาเหมือนเดิม"""
    doc = upload(client, "ใบเบิก.pdf", pages=1)
    created = sheet_from(client, doc)
    assert client.get("/api/pageinfo/" + created["doc_id"]).get_json()["pages"] == 1

    replace_upload(client, "ใบเบิก.pdf", pages=3)

    after = client.get("/api/pageinfo/" + created["doc_id"]).get_json()
    assert after["pages"] == 1, "ใบงานเก่าต้องยังอยู่กับฟอร์มเดิม"
    assert client.post("/api/fill", headers=hdr(client), json={
        "doc": created["doc_id"], "sheet": created["sheet"], "fields": fields(),
    }).status_code == 200

    got = client.get("/api/sheets/" + created["sheet"]).get_json()
    assert got["source_changed"] is True, "แต่ต้องบอกผู้ใช้ว่าฟอร์มต้นฉบับเปลี่ยนแล้ว"
    assert got["form_sha"] == created["form_sha"]


def test_relink_moves_the_sheet_onto_the_new_form(client, licensed):
    doc = upload(client, "ใบเบิก.pdf", pages=1)
    created = sheet_from(client, doc)
    replace_upload(client, "ใบเบิก.pdf", pages=3)

    body = client.post(
        "/api/sheets/" + created["sheet"] + "/relink", headers=hdr(client)
    ).get_json()
    assert body["form_sha"] != created["form_sha"]
    assert body["source_changed"] is False
    assert body["fields"][0]["value"] == "โรงเรียนวัดตัวอย่าง", "ค่าที่กรอกต้องอยู่ครบ"
    assert client.get("/api/pageinfo/" + body["doc_id"]).get_json()["pages"] == 3
    # สแนปช็อตเก่าที่ไม่มีใครอ้างแล้วต้องถูกเก็บกวาด
    assert len(list(forms_dir(client).glob("*.pdf"))) == 1


def test_relink_keeps_the_old_snapshot_for_other_sheets(client, licensed):
    doc = upload(client, "ใบเบิก.pdf", pages=1)
    a = sheet_from(client, doc)
    b = sheet_from(client, doc)
    replace_upload(client, "ใบเบิก.pdf", pages=3)

    client.post("/api/sheets/" + a["sheet"] + "/relink", headers=hdr(client))
    still = client.get("/api/sheets/" + b["sheet"]).get_json()
    assert still["form_sha"] == a["form_sha"]
    assert client.get("/api/pageinfo/" + still["doc_id"]).status_code == 200
    assert len(list(forms_dir(client).glob("*.pdf"))) == 2


def test_relink_is_a_no_op_when_the_form_is_unchanged(client, licensed):
    doc = upload(client, "ใบเบิก.pdf", pages=1)
    created = sheet_from(client, doc)
    body = client.post(
        "/api/sheets/" + created["sheet"] + "/relink", headers=hdr(client)
    ).get_json()
    assert body["form_sha"] == created["form_sha"]
    assert len(list(forms_dir(client).glob("*.pdf"))) == 1


def test_relink_refuses_a_tampered_trial_form(client):
    """แพ็กทดลองล็อกด้วยเนื้อไฟล์ — เอาไฟล์อื่นมาสวมชื่อแล้วย้ายใบงานไปใช้ไม่ได้"""
    created = create_sheet(client).get_json()
    A._pdf_path("local", "demo-leave.pdf").write_bytes(make_pdf(3))
    r = client.post("/api/sheets/" + created["sheet"] + "/relink", headers=hdr(client))
    assert r.status_code == 402
    assert client.get("/api/sheets/" + created["sheet"]).get_json()["form_sha"] == created["form_sha"]


def test_missing_source_is_reported_not_fatal(client):
    created = create_sheet(client).get_json()
    A._pdf_path("local", "demo-leave.pdf").unlink()

    got = client.get("/api/sheets/" + created["sheet"]).get_json()
    assert got["source_present"] is False
    assert got["source_changed"] is False
    # ใบงานยังเปิดและพิมพ์ได้ เพราะสแนปช็อตยังอยู่
    assert client.get("/api/pageinfo/" + created["doc_id"]).status_code == 200
    assert client.post("/api/sheets/" + created["sheet"] + "/relink",
                       headers=hdr(client)).status_code == 404


def test_relink_needs_csrf(client):
    created = create_sheet(client).get_json()
    assert client.post("/api/sheets/" + created["sheet"] + "/relink").status_code == 403
