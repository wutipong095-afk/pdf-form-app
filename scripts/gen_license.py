"""ออกคีย์ไลเซนต์จากรหัสเครื่องลูกค้า (ฝั่งผู้ขายเท่านั้น)

ต้องมี private key — ห้ามแจกสคริปต์นี้พร้อม private key ให้ลูกค้า

ต้องระบุอายุทุกครั้ง — ไม่มีค่าเริ่มต้น

ตัวอย่าง:
  python scripts/gen_license.py A1B2C3D4E5F67890 --term 1
  python scripts/gen_license.py A1B2C3D4E5F67890 --term 5
  python scripts/gen_license.py A1B2C3D4E5F67890 --term 10
  python scripts/gen_license.py A1B2C3D4E5F67890 --days 400
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from envutil import load_dotenv  # noqa: E402

from license_core import (  # noqa: E402
    LICENSE_TERM_DAYS,
    MAX_ISSUE_DAYS,
    TERM_CHOICES_TEXT,
    issue_license_key,
    resolve_issue_days,
)

_TERM_CHOICES = tuple(sorted(LICENSE_TERM_DAYS))
_TERM_HELP = "/".join(str(y) for y in _TERM_CHOICES)


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="ออกคีย์ไลเซนต์ PDF Form Marker (Ed25519)",
    )
    p.add_argument("machine_id", help="รหัสเครื่อง 16 ตัวจากหน้าแอปลูกค้า")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument(
        "--term",
        type=int,
        choices=_TERM_CHOICES,
        metavar=TERM_CHOICES_TEXT,
        help=f"อายุคีย์เป็นปี ตามแถวที่ลูกค้าจ่าย ({_TERM_HELP})",
    )
    g.add_argument(
        "--days",
        type=int,
        metavar="N",
        help=f"อายุเป็นวัน สำหรับยกวันที่เหลือตอนย้ายเครื่อง (0-{MAX_ISSUE_DAYS}; 0 = วันหมดอายุ UTC)",
    )
    return p.parse_args(argv)


def describe_key(key: str, days: int, term: Optional[int]) -> str:
    """อ่านวันหมดอายุจากคีย์ที่ออกจริง — เรียก now() ซ้ำจะเพี้ยน 1 วันถ้ารันคร่อมเที่ยงคืน UTC

    ป้าย "อายุ N ปี" ใช้เฉพาะตอนสั่ง --term เพราะ --days 1825 ตอนย้ายเครื่อง
    ไม่ใช่การขายแถว 5 ปี — ทะเบียนต้องแยกสองเคสนี้ออกจากกัน
    """
    exp = datetime.strptime(key.split(".")[2], "%Y%m%d").date().isoformat()
    if term is not None:
        return f"อายุ {term} ปี ({days} วัน) หมดอายุ {exp} UTC"
    return f"อายุกำหนดเอง {days} วัน หมดอายุ {exp} UTC"


def main(argv: Optional[list[str]] = None) -> int:
    load_dotenv()
    args = parse_args(argv)
    try:
        days = resolve_issue_days(args.term, args.days)
        key = issue_license_key(args.machine_id, days=days)
    except (ValueError, RuntimeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(describe_key(key, days, args.term), file=sys.stderr)
    print(key)
    return 0


if __name__ == "__main__":
    sys.exit(main())
