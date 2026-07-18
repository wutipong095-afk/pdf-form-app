"""ออกคีย์ไลเซนต์จากรหัสเครื่องลูกค้า (ฝั่งผู้ขายเท่านั้น)

ต้องมี private key — ห้ามแจกสคริปต์นี้พร้อม private key ให้ลูกค้า

ตัวอย่าง:
  python scripts/gen_license.py A1B2C3D4E5F67890
  python scripts/gen_license.py A1B2C3D4E5F67890 --days 1825
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from envutil import load_dotenv  # noqa: E402

load_dotenv()

from license_core import DEFAULT_SUPPORT_DAYS, issue_license_key  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description="ออกคีย์ไลเซนต์ PDF Form Marker (Ed25519)")
    p.add_argument("machine_id", help="รหัสเครื่อง 16 ตัวจากหน้าแอปลูกค้า")
    p.add_argument(
        "--days",
        type=int,
        default=DEFAULT_SUPPORT_DAYS,
        help=f"อายุการดูแล (วัน) ค่าเริ่มต้น {DEFAULT_SUPPORT_DAYS} (ราว 5 ปี)",
    )
    args = p.parse_args()
    try:
        print(issue_license_key(args.machine_id, days=args.days))
    except (ValueError, RuntimeError) as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
