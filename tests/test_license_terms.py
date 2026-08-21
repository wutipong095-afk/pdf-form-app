"""ออกคีย์ตามช่วงอายุที่ขาย — 1 / 3 / 5 / 10 ปี"""
from __future__ import annotations

import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from license_core import (  # noqa: E402
    LICENSE_TERM_DAYS,
    MAX_ISSUE_DAYS,
    TERM_CHOICES_TEXT,
    days_for_term_years,
    issue_license_key,
    load_public_key,
    parse_and_verify_key,
    resolve_issue_days,
)
from scripts.gen_license import describe_key, main, parse_args  # noqa: E402

MID = "A1B2C3D4E5F67890"


def expiry_of(key: str) -> date:
    return datetime.strptime(key.split(".")[2], "%Y%m%d").date()


def issue_with_window(days: int, priv: Ed25519PrivateKey) -> tuple[str, set[date]]:
    """ออกคีย์คร่อมเที่ยงคืน UTC ได้ — วันหมดอายุที่ยอมรับจึงมีได้สองค่า"""
    before = datetime.now(timezone.utc)
    key = issue_license_key(MID, days=days, private_key=priv)
    after = datetime.now(timezone.utc)
    return key, {(before + timedelta(days=days)).date(), (after + timedelta(days=days)).date()}


@pytest.fixture()
def vendor_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Ed25519PrivateKey:
    """คีย์ผู้ขายชั่วคราว + ชี้ฝั่งตรวจไปที่ public key คู่เดียวกัน"""
    priv = Ed25519PrivateKey.generate()
    pem = tmp_path / "license_public.pem"
    pem.write_bytes(
        priv.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    monkeypatch.setenv("LICENSE_PUBLIC_KEY_PATH", str(pem))
    load_public_key.cache_clear()
    yield priv
    load_public_key.cache_clear()


def test_sold_terms_map_to_days():
    assert LICENSE_TERM_DAYS == {1: 365, 3: 1095, 5: 1825, 10: 3650}
    for years, days in LICENSE_TERM_DAYS.items():
        assert days_for_term_years(years) == days


def test_unknown_term_is_rejected():
    with pytest.raises(ValueError, match="1, 3, 5, 10"):
        days_for_term_years(2)


def test_choice_text_follows_the_table():
    assert TERM_CHOICES_TEXT == "{1,3,5,10}"
    assert MAX_ISSUE_DAYS == LICENSE_TERM_DAYS[10]


@pytest.mark.parametrize("years", sorted(LICENSE_TERM_DAYS))
def test_issued_key_expiry_matches_term(years: int):
    priv = Ed25519PrivateKey.generate()
    days = days_for_term_years(years)
    key, allowed = issue_with_window(days, priv)
    assert expiry_of(key) in allowed


def test_each_term_gets_a_different_expiry():
    priv = Ed25519PrivateKey.generate()
    expiries = {
        expiry_of(issue_license_key(MID, days=days_for_term_years(y), private_key=priv))
        for y in LICENSE_TERM_DAYS
    }
    assert len(expiries) == len(LICENSE_TERM_DAYS)


def test_issued_key_verifies_against_the_matching_public_key(vendor_key):
    """round-trip — จับได้ถ้ารูปแบบ payload หรือการเซ็นเปลี่ยน ไม่ใช่ดูแค่ฟิลด์ exp"""
    days = days_for_term_years(5)
    key = issue_license_key(MID, days=days, private_key=vendor_key)
    info = parse_and_verify_key(key, MID)
    assert info["machine_id"] == MID
    assert info["expires"] == expiry_of(key).isoformat()
    assert info["days_left"] in (days - 1, days)
    assert info["key"] == key


def test_key_signed_by_another_vendor_is_rejected(vendor_key):
    stranger = Ed25519PrivateKey.generate()
    key = issue_license_key(MID, days=365, private_key=stranger)
    with pytest.raises(ValueError):
        parse_and_verify_key(key, MID)


def test_key_is_bound_to_one_machine(vendor_key):
    key = issue_license_key(MID, days=365, private_key=vendor_key)
    with pytest.raises(ValueError):
        parse_and_verify_key(key, "0123456789ABCDEF")


def test_transfer_on_expiry_calendar_day_uses_days_zero(vendor_key):
    """วันหมดอายุ UTC ยังใช้ได้ถึงสิ้นวัน — days_left = 0 ต้องออกคีย์ใหม่ได้"""
    key, allowed = issue_with_window(0, vendor_key)
    info = parse_and_verify_key(key, MID)
    assert info["expires"] in {d.isoformat() for d in allowed}
    assert info["days_left"] == 0


def test_must_pick_term_or_days():
    with pytest.raises(ValueError, match="--term"):
        resolve_issue_days(None, None)
    with pytest.raises(ValueError, match="--term"):
        resolve_issue_days(1, 365)
    assert resolve_issue_days(1, None) == 365
    assert resolve_issue_days(10, None) == 3650
    assert resolve_issue_days(None, 400) == 400
    assert resolve_issue_days(None, 0) == 0
    with pytest.raises(ValueError, match="--days"):
        resolve_issue_days(None, -1)


def test_days_cannot_exceed_the_longest_sold_row():
    """คีย์ที่ออกแล้วเพิกถอนไม่ได้ — พิมพ์ --days เกินต้องถูกปฏิเสธ ไม่ใช่ได้ที่นั่งถาวร"""
    assert resolve_issue_days(None, MAX_ISSUE_DAYS) == MAX_ISSUE_DAYS
    for bad in (MAX_ISSUE_DAYS + 1, 400000, 9999999):
        with pytest.raises(ValueError, match=str(MAX_ISSUE_DAYS)):
            resolve_issue_days(None, bad)


def test_issue_rejects_out_of_range_days():
    priv = Ed25519PrivateKey.generate()
    with pytest.raises(ValueError, match="days"):
        issue_license_key(MID, days=-1, private_key=priv)
    for bad in (MAX_ISSUE_DAYS + 1, 9999999):
        with pytest.raises(ValueError, match="days"):
            issue_license_key(MID, days=bad, private_key=priv)


def test_issue_requires_days_keyword():
    """days ต้องส่งเสมอ — ไม่มีค่าเริ่มต้น 5 ปี ให้พลาดโดยไม่ตั้งใจ"""
    priv = Ed25519PrivateKey.generate()
    with pytest.raises(TypeError):
        issue_license_key(MID, private_key=priv)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        issue_license_key(MID, 365, private_key=priv)  # type: ignore[misc]


def test_cli_requires_exactly_one_of_term_or_days():
    with pytest.raises(SystemExit):
        parse_args([MID])
    with pytest.raises(SystemExit):
        parse_args([MID, "--term", "5", "--days", "365"])
    with pytest.raises(SystemExit):
        parse_args([MID, "--term", "2"])
    assert parse_args([MID, "--term", "5"]).term == 5
    assert parse_args([MID, "--days", "400"]).days == 400
    assert parse_args([MID, "--days", "0"]).days == 0


def test_printed_expiry_is_read_from_the_issued_key():
    key = f"PFM2.{MID}.20310102.sig"
    assert "2031-01-02" in describe_key(key, 365, 1)


def test_days_transfer_is_never_labelled_as_a_sold_term():
    """--days 1825 ตอนย้ายเครื่องไม่ใช่การขายแถว 5 ปี"""
    key = f"PFM2.{MID}.20310102.sig"
    assert "กำหนดเอง 1825 วัน" in describe_key(key, 1825, None)
    assert "อายุ 5 ปี (1825 วัน)" in describe_key(key, 1825, 5)


def test_cli_rejects_oversized_days_without_a_traceback(capsys):
    assert main([MID, "--days", "9999999"]) == 1
    assert "error:" in capsys.readouterr().err


def test_cli_prints_no_term_line_when_issuing_fails(capsys):
    """ยืนยันอายุต้องพิมพ์หลังออกคีย์สำเร็จ ไม่ใช่ก่อน"""
    assert main(["NOTAHEXID", "--term", "5"]) == 1
    err = capsys.readouterr().err
    assert "error:" in err
    assert "อายุ 5 ปี" not in err
