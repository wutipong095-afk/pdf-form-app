"""โครงจุดและค่าที่กรอก — ใช้ร่วมกันระหว่างใบงาน เทมเพลต และไฟล์ .formdd

แยกออกมาเพื่อให้ sheet_core (รูปแบบเก็บงานปัจจุบัน) กับ job_core (ฟอร์แมต
ส่งออก/นำเข้า) ตรวจค่าด้วยกติกาเดียวกัน ไม่ต้องอ้างอิงกันเอง
"""
from __future__ import annotations

import math
import re
from datetime import date
from typing import Any

MAX_FIELDS = 500
MAX_VALUE_LEN = 2000
MAX_NAME_LEN = 80
MAX_PAGE = 9999
MAX_COORD = 1_000_000.0
MIN_SIZE = 0.1
MAX_SIZE = 1_000.0


class FormDataError(ValueError):
    """ค่าที่กรอก โครงจุด หรือไฟล์งานไม่ถูกต้อง"""


def _field_int(val: Any, default: int, *, lo: int, hi: int) -> int:
    if val is None or val == "":
        val = default
    try:
        n = int(val)
    except (TypeError, ValueError, OverflowError) as e:
        raise FormDataError("invalid field geometry") from e
    if not lo <= n <= hi:
        raise FormDataError("invalid field geometry")
    return n


def _field_float(val: Any, default: float, *, lo: float, hi: float) -> float:
    if val is None or val == "":
        val = default
    try:
        n = float(val)
    except (TypeError, ValueError, OverflowError) as e:
        raise FormDataError("invalid field geometry") from e
    # nan/inf เขียนเป็น JSON มาตรฐานไม่ได้ และทำให้ fill พังตอนวางข้อความ
    if not math.isfinite(n) or not lo <= n <= hi:
        raise FormDataError("invalid field geometry")
    return n


def normalize_fields(fields: Any) -> list[dict[str, Any]]:
    if not isinstance(fields, list):
        raise FormDataError("fields must be a list")
    if len(fields) > MAX_FIELDS:
        raise FormDataError("too many fields")
    out: list[dict[str, Any]] = []
    for item in fields:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        field = {
            "name": name[:MAX_NAME_LEN],
            "page": _field_int(item.get("page"), 0, lo=0, hi=MAX_PAGE),
            "x": _field_float(item.get("x"), 0, lo=-MAX_COORD, hi=MAX_COORD),
            "y": _field_float(item.get("y"), 0, lo=-MAX_COORD, hi=MAX_COORD),
            "size": _field_float(item.get("size"), 14, lo=MIN_SIZE, hi=MAX_SIZE),
            "value": str(item.get("value") or "")[:MAX_VALUE_LEN],
        }
        if "required" in item:
            field["required"] = item["required"] is True
        if "input_type" in item:
            kind = item["input_type"]
            if kind not in ("text", "number", "date"):
                raise FormDataError("invalid field type")
            field["input_type"] = kind
        if item.get("width") not in (None, ""):
            field["width"] = _field_float(item["width"], 100, lo=1, hi=MAX_COORD)
        out.append(field)
    return out


def layout_fields(fields: Any) -> list[dict[str, Any]]:
    """เทมเพลตเก็บโครงอย่างเดียว — ไม่เก็บค่าของใบนั้น"""
    out = []
    for f in normalize_fields(fields):
        f["value"] = ""
        out.append(f)
    return out


def first_value(fields: Any) -> str:
    """ค่าแรกที่ไม่ว่าง — ใช้ตั้งชื่อใบงานให้คนหาเจอ"""
    for f in fields or []:
        if not isinstance(f, dict):
            continue
        v = str(f.get("value") or "").strip()
        if v:
            return v
    return ""


def validate_completed_fields(fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return field-level errors; drafts may keep missing values until export."""
    errors = []
    for index, field in enumerate(fields):
        value = str(field.get("value") or "").strip()
        key = None
        if field.get("required") and not value:
            key = "flow.missing"
        elif value and field.get("input_type") == "number":
            if not re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)", value) or not math.isfinite(float(value)):
                key = "flow.badNumber"
        elif value and field.get("input_type") == "date":
            try:
                if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
                    raise ValueError("invalid date")
                date.fromisoformat(value)
            except ValueError:
                key = "flow.badDate"
        if key:
            errors.append({"index": index, "name": field["name"], "key": key})
    return errors


def required_off_page_errors(
    fields: list[dict[str, Any]],
    sizes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Required fields with a value must sit on a real page; optional orphans may skip."""
    errors = []
    for index, field in enumerate(fields):
        if not field.get("required"):
            continue
        if not str(field.get("value") or "").strip():
            continue
        page_no = field.get("page", 0)
        try:
            page_no = int(page_no)
        except (TypeError, ValueError):
            page_no = -1
        page = sizes[page_no] if 0 <= page_no < len(sizes) else None
        if page is None:
            errors.append({"index": index, "name": field["name"], "key": "flow.offPage"})
            continue
        x = field.get("x", 0)
        y = field.get("y", 0)
        try:
            w = float(page.get("w", 0))
            h = float(page.get("h", 0))
            x = float(x)
            y = float(y)
        except (TypeError, ValueError):
            errors.append({"index": index, "name": field["name"], "key": "flow.offPage"})
            continue
        if x < 0 or y < 0 or x >= w or y > h:
            errors.append({"index": index, "name": field["name"], "key": "flow.offPage"})
    return errors
