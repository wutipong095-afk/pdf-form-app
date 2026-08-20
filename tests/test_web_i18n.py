"""ภาษาของหน้าทดลองบนเว็บ — คีย์ไทย/อังกฤษต้องครบคู่ และหน้าไม่วาดไทยก่อนแล้วค่อยสลับ"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

WEBSITE = Path(__file__).resolve().parents[1] / "website"
I18N_JS = WEBSITE / "js" / "i18n.js"
APP_JS = WEBSITE / "js" / "app.js"
APP_HTML = WEBSITE / "app.html"

KEY_LINE = re.compile(r'^\s*"([\w.]+)":', re.MULTILINE)
T_CALL = re.compile(r'\bt\(\s*"([\w.]+)"')
HTML_KEY = re.compile(r'data-i18n(?:-html|-ph|-title|-alt)?="([\w.]+)"')


def catalogs() -> tuple[set[str], set[str]]:
    """คีย์ของบล็อก th และ en ใน i18n.js"""
    src = I18N_JS.read_text(encoding="utf-8")
    head, sep, tail = src.partition("\n    en: {")
    assert sep, "i18n.js ต้องมีบล็อก en"
    th_block = head.partition("\n    th: {")[2]
    en_block = tail.partition("\n    },")[0]
    return set(KEY_LINE.findall(th_block)), set(KEY_LINE.findall(en_block))


def test_thai_and_english_cover_the_same_keys():
    th, en = catalogs()
    assert th, "ไม่พบคีย์ในบล็อก th"
    assert th == en, f"ขาดใน en: {sorted(th - en)} · ขาดใน th: {sorted(en - th)}"


@pytest.mark.parametrize(
    "path, pattern",
    [(APP_JS, T_CALL), (APP_HTML, HTML_KEY)],
    ids=["app.js", "app.html"],
)
def test_every_key_used_exists_in_both_languages(path: Path, pattern: re.Pattern[str]):
    th, en = catalogs()
    used = set(pattern.findall(path.read_text(encoding="utf-8")))
    assert used, f"ไม่พบการเรียกคีย์ใน {path.name}"
    assert not (used - th), f"{path.name} เรียกคีย์ที่ไม่มีในภาษาไทย: {sorted(used - th)}"
    assert not (used - en), f"{path.name} เรียกคีย์ที่ไม่มีในภาษาอังกฤษ: {sorted(used - en)}"


def test_i18n_loads_in_head_before_app_js():
    """ต้องรู้ภาษาตั้งแต่ก่อนวาด body ไม่งั้นหน้าอังกฤษจะโชว์ไทยแวบหนึ่งก่อน"""
    html = APP_HTML.read_text(encoding="utf-8")
    i18n_at = html.index('src="js/i18n.js"')
    assert i18n_at < html.index("</head>"), "i18n.js ต้องอยู่ใน <head>"
    assert i18n_at < html.index('src="js/app.js"'), "i18n.js ต้องโหลดก่อน app.js"


def test_page_is_held_back_then_revealed():
    """คลาสที่ซ่อน body ต้องมีทั้งกฎ CSS คนใส่ และคนถอด ไม่งั้นหน้าค้างมองไม่เห็น"""
    html = APP_HTML.read_text(encoding="utf-8")
    js = I18N_JS.read_text(encoding="utf-8")
    assert "i18n-pending" in html
    assert 'classList.add("i18n-pending")' in js
    assert 'classList.remove("i18n-pending")' in js
    assert "DOMContentLoaded" in js, "ต้องมีตัวถอดสำรอง เผื่อ app.js ไม่โหลด"
