"""ใบงาน — JSON ค่าที่กรอกล้วน ๆ อ้างฟอร์มด้วย sha"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sheet_core  # noqa: E402
from fields_core import FormDataError  # noqa: E402

SHA = hashlib.sha256(b"form").hexdigest()
OTHER = hashlib.sha256(b"other").hexdigest()


def sample_fields():
    return [
        {"name": "หน่วยงาน", "page": 0, "x": 10, "y": 20, "size": 14, "value": "โรงเรียนวัดตัวอย่าง"},
        {"name": "ผู้เบิก", "page": 0, "x": 10, "y": 40, "size": 14, "value": ""},
    ]


def test_round_trip_keeps_thai(tmp_path: Path):
    path = tmp_path / "a.json"
    sheet_core.save_sheet(path, {
        "title": "ใบเบิก", "form_sha": SHA, "source_doc": "ใบเบิก.pdf",
        "template_name": "ใบเบิก", "fields": sample_fields(),
    })
    got = sheet_core.read_sheet(path)
    assert got["title"].startswith("ใบเบิก")
    assert got["form_sha"] == SHA
    assert got["fields"][0]["value"] == "โรงเรียนวัดตัวอย่าง"


def test_sheet_is_small_next_to_a_pdf(tmp_path: Path):
    path = tmp_path / "small.json"
    sheet_core.save_sheet(path, {
        "title": "ใบเบิก", "form_sha": SHA,
        "fields": [
            {"name": f"ช่อง{i}", "page": 0, "x": 1, "y": 2, "size": 14, "value": f"ค่า{i}"}
            for i in range(40)
        ],
    })
    assert path.stat().st_size < 32 * 1024


def test_update_keeps_fields_when_not_sent(tmp_path: Path):
    path = tmp_path / "b.json"
    sheet_core.save_sheet(path, {"title": "ก", "form_sha": SHA, "fields": sample_fields()})
    sheet_core.save_sheet(path, {"title": "ข", "rename": True})
    got = sheet_core.read_sheet(path)
    assert got["title"] == "ข"
    assert got["form_sha"] == SHA
    assert len(got["fields"]) == 2


def test_created_at_survives_updates(tmp_path: Path):
    path = tmp_path / "c.json"
    first = sheet_core.save_sheet(path, {"title": "ก", "form_sha": SHA, "fields": []})
    again = sheet_core.save_sheet(path, {"title": "ข"})
    assert again["created_at"] == first["created_at"]


def test_unique_names_do_not_collide(tmp_path: Path):
    names = {sheet_core.unique_sheet_name(tmp_path, "ใบเบิก", now=1_000_000) for _ in range(5)}
    assert len(names) == 5


def test_auto_title_appends_first_value():
    assert sheet_core.auto_title("ใบเบิก", [{"value": "สมชาย"}], "ใบเบิก") == "ใบเบิก — สมชาย"
    # ไม่ต่อซ้ำถ้าชื่ออยู่แล้ว
    assert sheet_core.auto_title("ใบเบิก สมชาย", [{"value": "สมชาย"}], "x") == "ใบเบิก สมชาย"
    assert sheet_core.auto_title("", [], "ใบลา") == "ใบลา"


def test_bad_or_missing_sha_rejected(tmp_path: Path):
    with pytest.raises(FormDataError, match="invalid form snapshot id"):
        sheet_core.save_sheet(tmp_path / "d.json", {"title": "ก", "form_sha": "nope"})


def test_corrupt_and_foreign_json_rejected(tmp_path: Path):
    bad = tmp_path / "e.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(FormDataError, match="could not read sheet file"):
        sheet_core.read_sheet(bad)
    foreign = tmp_path / "f.json"
    foreign.write_text(json.dumps({"kind": "something-else"}), encoding="utf-8")
    with pytest.raises(FormDataError, match="not a FromDD sheet"):
        sheet_core.read_sheet(foreign)


def test_missing_sheet_is_file_not_found(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        sheet_core.read_sheet(tmp_path / "gone.json")


def test_note_printed_records_output(tmp_path: Path):
    path = tmp_path / "g.json"
    sheet_core.save_sheet(path, {"title": "ก", "form_sha": SHA, "fields": sample_fields()})
    sheet_core.note_printed(path, "ใบเบิก-20260819-101010.pdf")
    sheet_core.note_printed(path, "ใบเบิก-20260819-101010.pdf")
    assert sheet_core.read_sheet(path)["printed"] == ["ใบเบิก-20260819-101010.pdf"]


def test_list_and_referenced_shas(tmp_path: Path):
    sheet_core.save_sheet(tmp_path / "one.json", {
        "title": "ใบเบิก", "form_sha": SHA, "template_name": "ใบเบิก", "fields": sample_fields(),
    })
    sheet_core.save_sheet(tmp_path / "two.json", {
        "title": "ใบลา", "form_sha": OTHER, "template_name": "ใบลา", "fields": [],
    })
    (tmp_path / "junk.json").write_text("{}", encoding="utf-8")

    rows = sheet_core.list_sheets(tmp_path)
    assert {r["name"] for r in rows} == {"one.json", "two.json"}
    one = next(r for r in rows if r["name"] == "one.json")
    assert one["kind"] == "sheet" and one["filled"] == 1 and one["pins"] == 2
    assert one["doc_id"].startswith("@form.")
    assert sheet_core.referenced_shas(tmp_path) == {SHA, OTHER}
    assert {r["name"] for r in sheet_core.list_sheets(tmp_path, "ใบลา")} == {"two.json"}


def test_auto_title_follows_the_values_not_the_template_box(tmp_path: Path):
    """ไคลเอนต์ส่งชื่อเทมเพลตมาทุกครั้ง — ต้องไม่ทับชื่อใบที่คิดจากค่าที่กรอก"""
    path = tmp_path / "auto.json"
    sheet_core.save_sheet(path, {
        "title_base": "ใบเบิก", "form_sha": SHA, "template_name": "ใบเบิก",
        "fields": [{"name": "ผู้เบิก", "page": 0, "x": 1, "y": 2, "size": 14, "value": "สมชาย"}],
    })
    assert sheet_core.read_sheet(path)["title"] == "ใบเบิก — สมชาย"

    # ออโต้เซฟรอบถัดไปส่ง title เป็นชื่อเทมเพลตมาด้วย
    sheet_core.save_sheet(path, {
        "title": "ใบเบิก", "template_name": "ใบเบิก",
        "fields": [{"name": "ผู้เบิก", "page": 0, "x": 1, "y": 2, "size": 14, "value": "สมหญิง"}],
    })
    got = sheet_core.read_sheet(path)
    assert got["title"] == "ใบเบิก — สมหญิง"
    # ไม่ต่อทับกันจนยาวขึ้นเรื่อย ๆ
    assert got["title"].count("—") == 1


def test_rename_sticks_and_stops_auto_naming(tmp_path: Path):
    path = tmp_path / "named.json"
    sheet_core.save_sheet(path, {
        "title_base": "ใบเบิก", "form_sha": SHA, "template_name": "ใบเบิก",
        "fields": [{"name": "ก", "page": 0, "x": 1, "y": 2, "size": 14, "value": "สมชาย"}],
    })
    sheet_core.save_sheet(path, {"title": "งานด่วนของ ผอ.", "rename": True})
    assert sheet_core.read_sheet(path)["title"] == "งานด่วนของ ผอ."

    sheet_core.save_sheet(path, {
        "title": "ใบเบิก", "template_name": "ใบเบิก",
        "fields": [{"name": "ก", "page": 0, "x": 1, "y": 2, "size": 14, "value": "คนอื่น"}],
    })
    assert sheet_core.read_sheet(path)["title"] == "งานด่วนของ ผอ."
