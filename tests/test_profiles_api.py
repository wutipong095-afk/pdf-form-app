"""เส้น /api/profiles + สมุดข้อมูลในไฟล์สำรอง — รันด้วย DATA_DIR ชั่วคราว ไม่แตะข้อมูลจริง"""
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
# ตั้งทับเสมอ — ห้าม setdefault: ถ้า dev export DATA_DIR ไว้ชี้ข้อมูลจริง เทสจะไปเขียนทับของจริง
if "pfm-tests-" not in os.environ.get("DATA_DIR", ""):
    _TEST_DATA_DIR = Path(tempfile.mkdtemp(prefix="pfm-tests-"))
    os.environ["DATA_DIR"] = str(_TEST_DATA_DIR)
    os.environ["LOG_DIR"] = str(_TEST_DATA_DIR / "logs")
else:
    _TEST_DATA_DIR = Path(os.environ["DATA_DIR"])

import app as A  # noqa: E402

# เทียบแบบ Path — เทียบสตริงพลาดได้เพราะ / กับ \ บนวินโดวส์
assert "pfm-tests-" in Path(A.DATA_DIR).resolve().as_posix(), (
    f"tests must not run against the real data dir (got {A.DATA_DIR})"
)


def test_suite_is_isolated_from_any_preset_data_dir():
    """กันเทสไปเขียนโฟลเดอร์ข้อมูลจริงถ้า dev export DATA_DIR ไว้"""
    data = Path(A.DATA_DIR).resolve()
    assert "pfm-tests-" in data.as_posix()
    assert data.parent == Path(tempfile.gettempdir()).resolve() or data.is_absolute()


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """ผู้ใช้ใหม่ต่อเทสหนึ่งตัว — เลี่ยงสมุดค้างข้ามเทส"""
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


def user_root(c) -> Path:
    return A.user_paths(A.LOCAL_USER)["root"]


def make(c, **kw):
    body = {"name": "โรงเรียนวัดตัวอย่าง", "kind": "org", "values": {"หน่วยงาน": "ร.ร.ตัวอย่าง"}}
    body.update(kw)
    return c.post("/api/profiles", headers=hdr(c), json=body)


# --- CRUD ---

def test_empty_book(client):
    assert client.get("/api/profiles").get_json() == {"version": 1, "profiles": []}


def test_create_read_update_delete(client):
    r = make(client)
    assert r.status_code == 200
    pid = r.get_json()["profile"]["id"]

    assert len(client.get("/api/profiles").get_json()["profiles"]) == 1

    r = client.put(f"/api/profiles/{pid}", headers=hdr(client),
                   json={"name": "ใหม่", "kind": "partner", "values": {"เรียน": "ผอ."}})
    assert r.get_json()["profile"] == {
        "id": pid, "name": "ใหม่", "kind": "partner", "values": {"เรียน": "ผอ."},
    }

    assert client.delete(f"/api/profiles/{pid}", headers=hdr(client, False)).status_code == 200
    assert client.get("/api/profiles").get_json()["profiles"] == []


def test_keys_are_trimmed_on_create(client):
    r = make(client, values={"  หน่วยงาน  ": "ค่า"})
    assert list(r.get_json()["profile"]["values"]) == ["หน่วยงาน"]


@pytest.mark.parametrize("body", [
    {"name": "", "kind": "org", "values": {}},
    {"name": "ก", "kind": "bogus", "values": {}},
    {"name": "ก", "kind": "org", "values": {" ": "ค"}},
    {"name": "ก", "kind": "org", "values": {"ข": "ค" * 501}},
    {"name": "ก", "kind": "org", "values": {"ข" * 81: "ค"}},
])
def test_invalid_payloads_are_rejected(client, body):
    r = client.post("/api/profiles", headers=hdr(client), json=body)
    assert r.status_code == 400
    assert r.get_json()["error"]


@pytest.mark.parametrize("bad_id", ["p-deadbeef", "..%2F..%2Fetc", "nope", "p-ZZZZ"])
def test_unknown_or_unsafe_ids_are_404(client, bad_id):
    assert client.put(f"/api/profiles/{bad_id}", headers=hdr(client),
                      json={"name": "ก", "kind": "org", "values": {}}).status_code == 404
    assert client.delete(f"/api/profiles/{bad_id}", headers=hdr(client, False)).status_code == 404


def test_writes_need_csrf(client):
    r = client.post("/api/profiles", headers={"Content-Type": "application/json"},
                    json={"name": "ก", "kind": "org", "values": {}})
    assert r.status_code == 403


# --- P1: ไฟล์เสียต้องไม่ถูกเขียนทับ ---

def test_damaged_book_reports_409_and_is_never_overwritten(client):
    make(client)
    path = user_root(client) / "profiles.json"
    damaged = path.read_text(encoding="utf-8")[:-5]  # ตัดท้ายให้ JSON พัง
    path.write_text(damaged, encoding="utf-8")

    r = client.get("/api/profiles")
    assert r.status_code == 409
    assert r.get_json()["unreadable"] is True

    assert client.post("/api/profiles", headers=hdr(client),
                       json={"name": "ใหม่", "kind": "org", "values": {}}).status_code == 409
    assert path.read_text(encoding="utf-8") == damaged, "ไฟล์เดิมต้องไม่ถูกแตะ"


# --- สำรอง / กู้คืน ---

def backup_zip(client) -> bytes:
    r = client.post("/api/backup", headers={"X-CSRF-Token": client._tok})
    assert r.status_code == 200
    return r.data


def restore(client, data: bytes, mode: str):
    return client.post(
        "/api/restore",
        headers={"X-CSRF-Token": client._tok},
        data={"file": (io.BytesIO(data), "b.zip"), "mode": mode},
        content_type="multipart/form-data",
    )


def test_backup_contains_the_book(client):
    make(client)
    names = zipfile.ZipFile(io.BytesIO(backup_zip(client))).namelist()
    assert "user/profiles.json" in names


def test_restore_brings_the_book_back_on_a_fresh_machine(client):
    make(client)
    data = backup_zip(client)
    (user_root(client) / "profiles.json").unlink()

    assert restore(client, data, "merge").status_code == 200
    assert len(client.get("/api/profiles").get_json()["profiles"]) == 1


def test_replace_mode_clears_the_old_book(client):
    """ZIP ไม่มีสมุด + โหมดแทนที่ = สมุดเก่าต้องหาย ไม่ค้าง"""
    empty_backup = backup_zip(client)  # ยังไม่มีโปรไฟล์
    make(client)
    assert len(client.get("/api/profiles").get_json()["profiles"]) == 1

    assert restore(client, empty_backup, "replace").status_code == 200
    assert client.get("/api/profiles").get_json()["profiles"] == []


def test_thai_named_templates_survive_a_restore_round_trip(client):
    """สระไทยเป็น combining mark — allowlist ของ ZIP ต้องไม่ตกไฟล์ชื่อไทย"""
    tpl = A.user_paths(A.LOCAL_USER)["templates"] / "แบบฟอร์มใบเบิก.json"
    tpl.write_text(json.dumps({"fields": []}, ensure_ascii=False), encoding="utf-8")
    data = backup_zip(client)
    tpl.unlink()

    r = restore(client, data, "merge")
    assert r.status_code == 200, r.get_json()
    assert tpl.is_file()


def test_docs_includes_font_metrics_for_preview(client):
    data = client.get("/api/docs").get_json()
    assert 0.5 < data["font_ascender"] < 1.5
    assert -1.0 < data["font_descender"] < 0


def test_docs_survives_unreadable_fill_font(client, monkeypatch):
    """FONT_PATH ชี้ไฟล์เสียต้องไม่ทำให้เปิดรายการเอกสารพังทั้งแอป"""
    def boom(_path):
        raise RuntimeError("FzErrorLibrary: font")

    monkeypatch.setattr(A, "_font_metrics", boom)
    r = client.get("/api/docs")
    assert r.status_code == 200
    data = r.get_json()
    assert data["font_ascender"] == 0.85
    assert data["font_descender"] == -0.25


def test_fill_font_bytes_match_thai_font(client):
    path = A.thai_font()
    assert path and os.path.isfile(path)
    r = client.get("/api/fill-font")
    assert r.status_code == 200
    assert r.data == Path(path).read_bytes()
    assert "font" in (r.content_type or "")


def test_index_font_face_url_is_cache_busted(client):
    html = client.get("/").get_data(as_text=True)
    assert f"/api/fill-font?v={A.fill_font_rev()}" in html
