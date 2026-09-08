#!/usr/bin/env python3
"""Assemble THIRD_PARTY_NOTICES.txt for the shipped application.

Sources of license text, in order of preference:
  * meta:<dist>  -> the LICENSE files installed with a Python distribution
  * tree:<dir>   -> curated license files already vendored under the repo
  * file:<path>  -> a hand-written notice (fonts, statically-linked OpenSSL)

Run from the repo root inside an environment that has the *runtime*
dependencies installed (requirements.txt), so metadata is resolvable:

    python scripts/collect_notices.py

The script fails loudly if any declared component yields no license text,
so the notices file can never silently ship incomplete.
"""
from __future__ import annotations

import importlib.metadata as ilm
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "THIRD_PARTY_NOTICES.txt"

# Only files that are actually license/notice text (never METADATA/RECORD/WHEEL).
_LICENSE_HINTS = ("LICENSE", "LICence", "COPYING", "NOTICE", "AUTHORS")
_KEEP_EXT = (".ijg",)
_SKIP = {"METADATA", "RECORD", "WHEEL", "top_level.txt", "entry_points.txt", "INSTALLER", "REQUESTED"}


def _looks_like_license(name: str, parent: str = "") -> bool:
    if name in _SKIP:
        return False
    up = name.upper()
    if any(h in up for h in ("LICENSE", "COPYING", "NOTICE", "AUTHORS")):
        return True
    if parent in ("BUILD_LICENSES", "LICENSES"):
        return True
    if name.endswith(_KEEP_EXT):
        return True
    if name == "bitstream-vera-license.txt":
        return True
    return False


def from_meta(dist: str) -> list[tuple[str, str]]:
    d = ilm.distribution(dist)
    out: list[tuple[str, str]] = []
    for f in d.files or []:
        if _looks_like_license(f.name):
            try:
                out.append((f.name, Path(f.locate()).read_text(encoding="utf-8", errors="replace")))
            except OSError:
                pass
    if not out:
        raise SystemExit(f"collect_notices: no license file found for distribution {dist!r}")
    return out


def from_tree(rel: str) -> list[tuple[str, str]]:
    base = ROOT / rel
    out: list[tuple[str, str]] = []
    for p in sorted(base.rglob("*")):
        if p.is_file() and _looks_like_license(p.name, p.parent.name):
            out.append((str(p.relative_to(base)), p.read_text(encoding="utf-8", errors="replace")))
    if not out:
        raise SystemExit(f"collect_notices: no license files under {rel!r}")
    return out


def from_file(rel: str) -> list[tuple[str, str]]:
    p = ROOT / rel
    if not p.is_file():
        raise SystemExit(f"collect_notices: missing notice file {rel!r}")
    return [(p.name, p.read_text(encoding="utf-8", errors="replace"))]


# (Section title, SPDX summary, [sources]) — order controls the output.
MANIFEST: list[tuple[str, str, list[tuple[str, str]]]] = [
    ("Noto Sans Thai (font)", "OFL-1.1", [("file", "notices/NotoSansThai.txt"), ("file", "notices/SIL-OFL-1.1.txt")]),
    ("TH Sarabun New (font)", "Free national font", [("file", "notices/THSarabun.txt")]),
    ("TH Sarabun IT๙ (font)", "Free national font (derivative)", [("file", "notices/THSarabunIT9.txt")]),
    ("pypdf", "BSD-3-Clause", [("tree", "third_party_licenses/pypdf")]),
    ("pypdfium2 (+ bundled PDFium build deps)", "Apache-2.0 / BSD-3-Clause", [("tree", "third_party_licenses/pypdfium2")]),
    ("ReportLab (+ Bitstream Vera fonts)", "BSD-3-Clause", [("tree", "third_party_licenses/reportlab")]),
    ("uharfbuzz / HarfBuzz", "MIT (Old)", [("tree", "third_party_licenses/uharfbuzz")]),
    ("fontTools", "MIT", [("tree", "third_party_licenses/fonttools")]),
    ("Pillow", "MIT-CMU", [("tree", "third_party_licenses/pillow")]),
    ("Flask", "BSD-3-Clause", [("meta", "Flask")]),
    ("Werkzeug", "BSD-3-Clause", [("meta", "Werkzeug")]),
    ("Jinja2", "BSD-3-Clause", [("meta", "Jinja2")]),
    ("click", "BSD-3-Clause", [("meta", "click")]),
    ("itsdangerous", "BSD-3-Clause", [("meta", "itsdangerous")]),
    ("MarkupSafe", "BSD-3-Clause", [("meta", "MarkupSafe")]),
    ("blinker", "MIT", [("meta", "blinker")]),
    ("waitress", "ZPL-2.1", [("meta", "waitress")]),
    ("cryptography", "Apache-2.0 / BSD-3-Clause", [("meta", "cryptography")]),
    ("cffi", "MIT", [("meta", "cffi")]),
    ("pycparser", "BSD-3-Clause", [("meta", "pycparser")]),
    ("OpenSSL (bundled by cryptography)", "Apache-2.0", [("file", "notices/OpenSSL.txt")]),
]

_READERS = {"meta": from_meta, "tree": from_tree, "file": from_file}


def build() -> str:
    rule = "=" * 78
    lines = [
        "THIRD-PARTY SOFTWARE NOTICES",
        "PDF Form Marker (FormDD)",
        "",
        "This application is distributed with the third-party components listed",
        "below. Each is used under its own license; the full license texts follow.",
        "The application itself and the documents it produces are not covered by",
        "these licenses.",
        "",
        "No GPL/AGPL (copyleft) components are shipped in the installed application.",
        "",
        rule,
        "",
    ]
    for title, spdx, sources in MANIFEST:
        lines.append(rule)
        lines.append(f"{title}   [{spdx}]")
        lines.append(rule)
        lines.append("")
        for kind, arg in sources:
            for label, text in _READERS[kind](arg):
                lines.append(f"--- {label} ---")
                lines.append(text.rstrip("\n"))
                lines.append("")
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


if __name__ == "__main__":
    text = build()
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(text):,} bytes, {len(MANIFEST)} components)")
    sys.exit(0)
