"""ออกคีย์ไลเซนต์จากรหัสเครื่องลูกค้า
ใช้ฝั่งผู้ขายเท่านั้น — ต้องตั้ง LICENSE_SECRET ให้ตรงกับที่อยู่ในตัวแอปลูกค้า

ตัวอย่าง:
  set LICENSE_SECRET=ความลับของคุณ
  python scripts/gen_license.py A1B2C3D4E5F67890
  python scripts/gen_license.py A1B2C3D4E5F67890 --days 1825
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# โหลด .env ของโปรเจกต์ (ถ้ามี)
env_path = ROOT / ".env"
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val

from license_core import DEFAULT_SUPPORT_DAYS, issue_license_key  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description="ออกคีย์ไลเซนต์ PDF Form Marker")
    p.add_argument("machine_id", help="รหัสเครื่อง 16 ตัว (จากหน้าแอปลูกค้า)")
    p.add_argument(
        "--days",
        type=int,
        default=DEFAULT_SUPPORT_DAYS,
        help=f"อายุการดูแล (วัน) ค่าเริ่มต้น {DEFAULT_SUPPORT_DAYS} ≈ 5 ปี",
    )
    args = p.parse_args()
    if not os.environ.get("LICENSE_SECRET") or os.environ.get("LICENSE_SECRET") == "pdf-form-marker-dev-secret-change-me":
        print("คำเตือน: ยังใช้ LICENSE_SECRET ค่าเริ่มต้น/ว่าง — ตั้งใน .env ก่อนขายจริง", file=sys.stderr)
    key = issue_license_key(args.machine_id, days=args.days)
    print(key)


if __name__ == "__main__":
    main()
