"""เขียน latest.json + SHA256SUMS.txt ข้าง Setup.exe ที่ตั้งชื่อตามเวอร์ชันแล้ว"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path

_SETUP_NAME_RE = re.compile(
    r"^(?:FormDD|PDFFormMarker)-Setup-(\d+\.\d+\.\d+(?:\.\d+)?)\.exe$",
    re.IGNORECASE,
)
_DEFAULT_URL_BASE = "https://formdd.xambrain.com/releases"


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def version_from_filename(name: str) -> str:
    m = _SETUP_NAME_RE.fullmatch(name)
    if not m:
        raise SystemExit(
            f"ชื่อไฟล์ต้องเป็น FormDD-Setup-x.y.z.exe (หรือ PDFFormMarker-Setup-x.y.z.exe): {name}"
        )
    return m.group(1)


def write_meta(
    setup: Path,
    *,
    url_base: str = _DEFAULT_URL_BASE,
    notes: str = "",
    published_at: str = "",
) -> tuple[Path, Path]:
    setup = setup.resolve()
    if not setup.is_file():
        raise SystemExit(f"ไม่พบไฟล์: {setup}")
    version = version_from_filename(setup.name)
    digest = sha256_file(setup)
    size = setup.stat().st_size
    base = url_base.rstrip("/")
    payload = {
        "version": version,
        "setup_url": f"{base}/{setup.name}",
        "sha256": digest,
        "size": size,
        "published_at": published_at or date.today().isoformat(),
        "notes": notes,
    }
    latest = setup.parent / "latest.json"
    sums = setup.parent / "SHA256SUMS.txt"
    latest.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    sums.write_text(f"{digest}  {setup.name}\n", encoding="utf-8")
    return latest, sums


def main() -> None:
    parser = argparse.ArgumentParser(description="Write latest.json and SHA256SUMS.txt next to a Setup.exe")
    parser.add_argument("setup", type=Path, help="Path to FormDD-Setup-x.y.z.exe")
    parser.add_argument("--url-base", default=_DEFAULT_URL_BASE)
    parser.add_argument("--notes", default="")
    parser.add_argument("--published-at", default="")
    args = parser.parse_args()
    latest, sums = write_meta(
        args.setup,
        url_base=args.url_base,
        notes=args.notes,
        published_at=args.published_at,
    )
    print(latest)
    print(sums)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
