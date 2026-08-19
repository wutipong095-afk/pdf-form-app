"""โครงจุดและค่าที่กรอก — กติกาที่ใบงาน เทมเพลต และ .fromdd ใช้ร่วมกัน"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fields_core import (  # noqa: E402
    MAX_FIELDS,
    FormDataError,
    first_value,
    layout_fields,
    normalize_fields,
)


def test_keeps_thai_values_and_drops_unnamed_pins():
    got = normalize_fields([
        {"name": "หน่วยงาน", "page": 1, "x": 10, "y": 20, "size": 14, "value": "โรงเรียนวัดตัวอย่าง"},
        {"name": "  ", "page": 0, "x": 1, "y": 1, "value": "ข้าม"},
        "ไม่ใช่ dict",
    ])
    assert len(got) == 1
    assert got[0]["name"] == "หน่วยงาน"
    assert got[0]["value"] == "โรงเรียนวัดตัวอย่าง"
    assert got[0]["page"] == 1


def test_layout_strips_values_but_keeps_geometry():
    got = layout_fields([{"name": "ก", "page": 2, "x": 5, "y": 6, "size": 12, "value": "ค่า"}])
    assert got[0]["value"] == ""
    assert (got[0]["page"], got[0]["x"], got[0]["size"]) == (2, 5.0, 12.0)


def test_bad_geometry_is_form_data_error():
    for bad in ({"page": "2.0"}, {"x": "abc"}, {"x": "nan"}, {"y": "inf"}, {"size": "1e400"}):
        with pytest.raises(FormDataError, match="invalid field geometry"):
            normalize_fields([{"name": "a", "page": 0, "x": 1, "y": 1, "size": 14, **bad}])


def test_page_and_size_ranges():
    for bad in ({"page": -1}, {"page": 10**20}, {"size": 0}, {"size": -1}, {"size": 5000}):
        with pytest.raises(FormDataError, match="invalid field geometry"):
            normalize_fields([{"name": "a", "page": 0, "x": 1, "y": 1, "size": 14, **bad}])
    ok = normalize_fields([{"name": "a", "page": 0, "x": -50, "y": 1, "size": 8}])
    assert ok[0]["x"] == -50 and ok[0]["size"] == 8


def test_too_many_fields_rejected():
    ok = [{"name": f"f{i}", "page": 0, "x": 1, "y": 1} for i in range(MAX_FIELDS)]
    assert len(normalize_fields(ok)) == MAX_FIELDS
    with pytest.raises(FormDataError, match="too many fields"):
        normalize_fields(ok + [{"name": "over", "page": 0, "x": 1, "y": 1}])


def test_fields_must_be_a_list():
    with pytest.raises(FormDataError, match="fields must be a list"):
        normalize_fields({"name": "a"})


def test_first_value_picks_first_non_empty():
    assert first_value([{"value": "  "}, {"value": "สมชาย"}, {"value": "ข"}]) == "สมชาย"
    assert first_value([]) == ""
    assert first_value([{"value": ""}]) == ""
