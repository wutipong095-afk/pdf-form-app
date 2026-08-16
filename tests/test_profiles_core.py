"""สมุดข้อมูลล่วงหน้า — validate, ขีดจำกัด, และกฎ "ไฟล์เสียห้ามเขียนทับ" """
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from profiles_core import (  # noqa: E402
    MAX_KEY_LEN,
    MAX_PROFILES,
    MAX_VALUE_LEN,
    ProfilesUnreadable,
    create_profile,
    delete_profile,
    load_profiles,
    profiles_path,
    save_profiles,
    update_profile,
    validate_payload,
)


@pytest.fixture()
def root(tmp_path: Path) -> Path:
    return tmp_path


def write_raw(root: Path, text: str) -> None:
    profiles_path(root).write_text(text, encoding="utf-8")


# --- อ่าน/เขียน ---

def test_missing_file_is_an_empty_book(root: Path):
    assert load_profiles(root) == {"version": 1, "profiles": []}


def test_round_trip_keeps_thai_text(root: Path):
    p = create_profile(root, {
        "name": "โรงเรียนวัดตัวอย่าง",
        "kind": "org",
        "values": {"หน่วยงาน": "โรงเรียนวัดตัวอย่าง", "เรียน": "ผู้อำนวยการ"},
    })
    assert p["id"].startswith("p-")
    again = load_profiles(root)["profiles"]
    assert again == [p]


def test_save_is_atomic_and_leaves_no_temp_files(root: Path):
    create_profile(root, {"name": "ก", "kind": "org", "values": {}})
    leftovers = [q.name for q in root.iterdir() if q.name.startswith(".profiles-")]
    assert leftovers == []


# --- P1: ไฟล์อ่านไม่ได้ ต้องไม่กลายเป็นสมุดว่างแล้วโดนเขียนทับ ---

@pytest.mark.parametrize("bad", [
    "{ not json",
    "[]",
    '{"profiles": "nope"}',
    '{"profiles": [{"name": "ไม่มี id"}]}',
    '{"profiles": [{"id": "p-1", "name": "ก", "values": {"k": ["list"]}}]}',
    # คีย์สองตัวที่ trim แล้วชนกัน — เคยกลืนเหลือตัวเดียวเงียบ ๆ
    '{"profiles": [{"id": "p-1", "name": "ก", "values": {"หน่วยงาน": "1", " หน่วยงาน ": "2"}}]}',
    '{"profiles": [{"id": "p-1", "name": "ก", "values": {"  ": "ค่า"}}]}',
])
def test_damaged_file_raises_instead_of_reading_empty(root: Path, bad: str):
    write_raw(root, bad)
    with pytest.raises(ProfilesUnreadable):
        load_profiles(root)


def test_colliding_keys_never_lose_a_value_on_resave(root: Path):
    """trim ชนกันแล้วเซฟทับ = ค่าหนึ่งหายถาวร — ต้องปฏิเสธตั้งแต่อ่าน"""
    raw = json.dumps({"version": 1, "profiles": [{
        "id": "p-aaaaaaaa", "name": "ก", "kind": "org",
        "values": {"หน่วยงาน": "ค่าที่หนึ่ง", " หน่วยงาน ": "ค่าที่สอง"},
    }]}, ensure_ascii=False)
    write_raw(root, raw)
    with pytest.raises(ProfilesUnreadable):
        create_profile(root, {"name": "ใหม่", "kind": "org", "values": {}})
    assert profiles_path(root).read_text(encoding="utf-8") == raw


def test_oversized_file_raises(root: Path, monkeypatch):
    monkeypatch.setattr("profiles_core.MAX_FILE_BYTES", 10)
    write_raw(root, json.dumps({"version": 1, "profiles": []}) + " " * 50)
    with pytest.raises(ProfilesUnreadable):
        load_profiles(root)


def test_a_book_at_full_size_limits_still_loads(root: Path):
    """ขีดจำกัดที่ validate ยอมรับต้องไม่ทำให้ไฟล์ถูกต้องกลายเป็น 'อ่านไม่ได้'"""
    profiles = [
        {
            "id": f"p-{i:08x}",
            "name": "ก" * 120,
            "kind": "org",
            "values": {"ค" * MAX_KEY_LEN + str(k): "ง" * MAX_VALUE_LEN for k in range(60)},
        }
        for i in range(MAX_PROFILES)
    ]
    save_profiles(root, {"profiles": profiles})
    size = profiles_path(root).stat().st_size
    loaded = load_profiles(root)
    assert len(loaded["profiles"]) == MAX_PROFILES, f"file of {size} bytes must still load"


def test_damaged_file_blocks_writes_so_data_survives(root: Path):
    original = '{"profiles": [{"id": "p-aaaaaaaa", "name": "ของเดิม", "kind": "org", "values": {"ก": "ข"}}], "trailing'
    write_raw(root, original)
    for call in (
        lambda: create_profile(root, {"name": "ใหม่", "kind": "org", "values": {}}),
        lambda: update_profile(root, "p-aaaaaaaa", {"name": "ใหม่", "kind": "org", "values": {}}),
        lambda: delete_profile(root, "p-aaaaaaaa"),
    ):
        with pytest.raises(ProfilesUnreadable):
            call()
    assert profiles_path(root).read_text(encoding="utf-8") == original


def test_book_over_the_count_limit_is_not_truncated_on_read(root: Path):
    """ตัดตอนอ่านแล้วเซฟทับ = โปรไฟล์ส่วนเกินหายถาวร"""
    profiles = [
        {"id": f"p-{i:08x}", "name": f"n{i}", "kind": "org", "values": {}}
        for i in range(MAX_PROFILES + 5)
    ]
    save_profiles(root, {"profiles": profiles})
    assert len(load_profiles(root)["profiles"]) == MAX_PROFILES + 5


# --- validate ---

def test_key_and_name_are_trimmed(root: Path):
    _, _, values = validate_payload({"name": "  ก  ", "kind": "org", "values": {"  ข  ": "ค"}})
    assert list(values) == ["ข"]


@pytest.mark.parametrize("payload", [
    {"name": "", "kind": "org", "values": {}},
    {"name": "   ", "kind": "org", "values": {}},
    {"name": "ก", "kind": "unknown", "values": {}},
    {"name": "ก", "kind": "org", "values": {"  ": "ค"}},
    {"name": "ก", "kind": "org", "values": {"ข": "ค" * (MAX_VALUE_LEN + 1)}},
    {"name": "ก", "kind": "org", "values": {"ข" * (MAX_KEY_LEN + 1): "ค"}},
    {"name": "ก", "kind": "org", "values": "not a dict"},
    {"name": "ก", "kind": "org", "values": {"ข": {"nested": 1}}},
    "not an object",
])
def test_rejects_bad_payloads(payload):
    with pytest.raises(ValueError):
        validate_payload(payload)


def test_profile_count_is_capped(root: Path):
    for i in range(MAX_PROFILES):
        create_profile(root, {"name": f"n{i}", "kind": "org", "values": {}})
    with pytest.raises(ValueError):
        create_profile(root, {"name": "เกิน", "kind": "org", "values": {}})


def test_update_and_delete_unknown_id(root: Path):
    with pytest.raises(KeyError):
        update_profile(root, "p-deadbeef", {"name": "ก", "kind": "org", "values": {}})
    with pytest.raises(KeyError):
        delete_profile(root, "p-deadbeef")


def test_update_replaces_values_wholesale(root: Path):
    p = create_profile(root, {"name": "ก", "kind": "org", "values": {"เก่า": "1"}})
    updated = update_profile(root, p["id"], {"name": "ข", "kind": "person", "values": {"ใหม่": "2"}})
    assert updated == {"id": p["id"], "name": "ข", "kind": "person", "values": {"ใหม่": "2"}}
    assert load_profiles(root)["profiles"] == [updated]


def test_ids_are_unique_across_creates(root: Path):
    ids = {create_profile(root, {"name": f"n{i}", "kind": "org", "values": {}})["id"] for i in range(20)}
    assert len(ids) == 20
