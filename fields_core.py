"""โครงจุดและค่าที่กรอก — ใช้ร่วมกันระหว่างใบงาน เทมเพลต และไฟล์ .fromdd

แยกออกมาเพื่อให้ sheet_core (รูปแบบเก็บงานปัจจุบัน) กับ job_core (ฟอร์แมต
ส่งออก/นำเข้า) ตรวจค่าด้วยกติกาเดียวกัน ไม่ต้องอ้างอิงกันเอง
"""
from __future__ import annotations

import math
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
        out.append({
            "name": name[:MAX_NAME_LEN],
            "page": _field_int(item.get("page"), 0, lo=0, hi=MAX_PAGE),
            "x": _field_float(item.get("x"), 0, lo=-MAX_COORD, hi=MAX_COORD),
            "y": _field_float(item.get("y"), 0, lo=-MAX_COORD, hi=MAX_COORD),
            "size": _field_float(item.get("size"), 14, lo=MIN_SIZE, hi=MAX_SIZE),
            "value": str(item.get("value") or "")[:MAX_VALUE_LEN],
        })
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
