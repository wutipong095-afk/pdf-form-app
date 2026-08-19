"""เส้น /api/jobs + ประวัติไฟล์งาน — รันด้วย DATA_DIR ชั่วคราว ไม่แตะข้อมูลจริง"""
from __future__ import annotations

import io
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
    return c


def hdr(c, json_body=True):
    h = {"X-CSRF-Token": c._tok}
    if json_body:
        h["Content-Type"] = "application/json"
    return h


def fields(value="โรงเรียนวัดตัวอย่าง"):
    return [{"name": "หน่วยงาน", "page": 0, "x": 114, "y": 100, "size": 14, "value": value}]


def create_job(c, value="โรงเรียนวัดตัวอย่าง"):
    return c.post("/api/jobs", headers=hdr(c), json={
        "source_doc": "demo-leave.pdf",
        "title": "ใบลา",
        "template_name": "demo-ใบลา",
        "fields": fields(value),
    })


def test_create_and_reload_job(client):
    r = create_job(client)
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body["file"].endswith(".fromdd")
    assert body["fields"][0]["value"] == "โรงเรียนวัดตัวอย่าง"
    assert body["source_doc"] == "demo-leave.pdf"

    got = client.get("/api/jobs/" + body["file"])
    assert got.status_code == 200
    assert got.get_json()["fields"][0]["value"] == "โรงเรียนวัดตัวอย่าง"


def test_update_job_keeps_values(client):
    created = create_job(client).get_json()
    r = client.post("/api/jobs", headers=hdr(client), json={
        "job": created["file"],
        "fields": fields("ค่าใหม่"),
    })
    assert r.status_code == 200
    assert r.get_json()["fields"][0]["value"] == "ค่าใหม่"
    assert r.get_json()["file"] == created["file"]


def test_history_lists_jobs(client):
    created = create_job(client).get_json()
    hist = client.get("/api/history").get_json()
    names = [f["name"] for f in hist["files"]]
    assert created["file"] in names
    job = next(f for f in hist["files"] if f["name"] == created["file"])
    assert job["kind"] == "job"
    assert job["doc_id"].startswith("@job.")


FONT = Path(__file__).resolve().parents[1] / "fonts" / "THSarabun.ttf"


def test_fill_from_job_and_not_from_printed_pdf(client):
    if not FONT.is_file():
        pytest.skip("THSarabun.ttf not in fonts/")
    created = create_job(client).get_json()
    filled = client.post("/api/fill", headers=hdr(client), json={
        "doc": created["doc_id"],
        "fields": fields("โรงเรียนวัดตัวอย่าง"),
        "outname": "ใบลา",
    })
    assert filled.status_code == 200, filled.get_json()
    out = filled.get_json()["file"]
    assert out.endswith(".pdf")

    blocked = client.post("/api/fill", headers=hdr(client), json={
        "doc": "@out." + out,
        "fields": fields("ทับ"),
    })
    assert blocked.status_code == 400


def test_template_save_strips_values(client):
    r = client.post("/api/template/demo-ใบลา", headers=hdr(client), json={
        "doc": "demo-leave.pdf",
        "fields": fields("ต้องไม่ถูกเก็บ"),
    })
    assert r.status_code == 200, r.get_json()
    saved = client.get("/api/template/demo-ใบลา").get_json()
    assert saved["fields"][0]["value"] == ""


def test_backup_includes_job_file(client):
    created = create_job(client).get_json()
    r = client.post("/api/backup", headers={"X-CSRF-Token": client._tok})
    assert r.status_code == 200
    names = zipfile.ZipFile(io.BytesIO(r.data)).namelist()
    assert f"user/jobs/{created['file']}" in names


def test_job_needs_csrf(client):
    r = client.post("/api/jobs", headers={"Content-Type": "application/json"}, json={
        "source_doc": "demo-leave.pdf",
        "title": "ก",
        "fields": fields(),
    })
    assert r.status_code == 403


def test_invalid_field_geometry_is_400(client):
    r = client.post("/api/jobs", headers=hdr(client), json={
        "source_doc": "demo-leave.pdf",
        "title": "ใบลา",
        "fields": [{"name": "หน่วยงาน", "page": "2.0", "x": 1, "y": 1, "size": 14, "value": "ก"}],
    })
    assert r.status_code == 400
    assert r.get_json()["error"]


def test_failed_create_leaves_no_empty_job_file(client, tmp_path, monkeypatch):
    def boom(*a, **k):
        raise A.JobError("boom")

    monkeypatch.setattr(A, "save_job", boom)
    r = create_job(client)
    assert r.status_code == 400
    # unique_job_name จองชื่อไว้ก่อนเขียน — ต้องไม่มีไฟล์ค้าง
    assert not list(tmp_path.rglob("*.fromdd"))
