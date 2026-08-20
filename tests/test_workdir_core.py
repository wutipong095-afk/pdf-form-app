"""โฟลเดอร์เก็บงานที่ผู้ใช้เลือกเอง"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import workdir_core  # noqa: E402
from workdir_core import WorkDirError  # noqa: E402


@pytest.fixture(autouse=True)
def no_cache():
    workdir_core._RESOLVED.clear()
    yield
    workdir_core._RESOLVED.clear()


def test_default_is_the_user_folder(tmp_path: Path):
    root = tmp_path / "user"
    root.mkdir()
    assert workdir_core.resolve(root) == root
    st = workdir_core.status(root)
    assert st["custom"] is False and st["unavailable"] is False


def test_set_moves_existing_work_along(tmp_path: Path):
    root = tmp_path / "user"
    (root / "sheets").mkdir(parents=True)
    (root / "forms").mkdir()
    (root / "output").mkdir()
    (root / "sheets" / "ใบเบิก.json").write_text("{}", encoding="utf-8")
    (root / "forms" / "abc.pdf").write_bytes(b"%PDF-1")
    (root / "output" / "พิมพ์แล้ว.pdf").write_bytes(b"%PDF-2")

    dest = tmp_path / "Documents" / "FromDD"
    out = workdir_core.set_work_dir(root, str(dest))

    assert out["moved"] == 3
    assert out["custom"] is True
    assert (dest / "sheets" / "ใบเบิก.json").is_file()
    assert (dest / "forms" / "abc.pdf").read_bytes() == b"%PDF-1"
    assert (dest / "output" / "พิมพ์แล้ว.pdf").is_file()
    # ของเดิมย้ายไปแล้ว ไม่ทิ้งสำเนาไว้
    assert not (root / "sheets" / "ใบเบิก.json").exists()
    assert workdir_core.resolve(root) == dest.resolve()


def test_reset_moves_the_work_back(tmp_path: Path):
    root = tmp_path / "user"
    root.mkdir()
    dest = tmp_path / "Documents" / "FromDD"
    workdir_core.set_work_dir(root, str(dest))
    (dest / "sheets" / "ก.json").write_text("{}", encoding="utf-8")

    out = workdir_core.reset(root)
    assert out["custom"] is False
    assert (root / "sheets" / "ก.json").is_file()
    assert workdir_core.resolve(root) == root


def test_never_overwrites_a_file_already_there(tmp_path: Path):
    root = tmp_path / "user"
    (root / "sheets").mkdir(parents=True)
    (root / "sheets" / "ชนกัน.json").write_text("ของใหม่", encoding="utf-8")
    dest = tmp_path / "dest"
    (dest / "sheets").mkdir(parents=True)
    (dest / "sheets" / "ชนกัน.json").write_text("ของเดิม", encoding="utf-8")

    out = workdir_core.set_work_dir(root, str(dest))
    assert out["moved"] == 0
    assert (dest / "sheets" / "ชนกัน.json").read_text(encoding="utf-8") == "ของเดิม"


def test_refuses_the_program_folder(tmp_path: Path):
    root = tmp_path / "user"
    root.mkdir()
    program = tmp_path / "Program Files" / "FromDD"
    program.mkdir(parents=True)
    with pytest.raises(WorkDirError, match="program folder"):
        workdir_core.set_work_dir(root, str(program / "data"), forbidden=(program,))
    with pytest.raises(WorkDirError, match="program folder"):
        workdir_core.set_work_dir(root, str(program), forbidden=(program,))


def test_refuses_a_file_and_an_empty_path(tmp_path: Path):
    root = tmp_path / "user"
    root.mkdir()
    afile = tmp_path / "ไม่ใช่โฟลเดอร์.txt"
    afile.write_text("x", encoding="utf-8")
    with pytest.raises(WorkDirError, match="directory"):
        workdir_core.set_work_dir(root, str(afile))
    with pytest.raises(WorkDirError, match="choose a folder"):
        workdir_core.set_work_dir(root, "   ")


def test_falls_back_when_the_folder_disappears(tmp_path: Path):
    """ไดรฟ์เครือข่ายหลุด — แอปต้องยังทำงานต่อได้ ไม่ใช่พังทั้งตัว"""
    root = tmp_path / "user"
    root.mkdir()
    dest = tmp_path / "ไดรฟ์ที่หายไป"
    workdir_core.set_work_dir(root, str(dest))
    assert workdir_core.resolve(root) == dest.resolve()

    import shutil

    shutil.rmtree(dest)
    workdir_core._RESOLVED.clear()

    def refuse(path):
        return False

    # จำลองว่าสร้างใหม่ไม่ได้ (ไดรฟ์ไม่อยู่) ไม่ใช่แค่โฟลเดอร์หาย
    original = workdir_core._usable
    workdir_core._usable = refuse
    try:
        assert workdir_core.resolve(root) == root
        st = workdir_core.status(root)
        assert st["unavailable"] is True
        assert st["configured_path"]
    finally:
        workdir_core._usable = original


def test_resolve_is_cached_between_calls(tmp_path: Path):
    root = tmp_path / "user"
    root.mkdir()
    dest = tmp_path / "dest"
    workdir_core.set_work_dir(root, str(dest))

    workdir_core._RESOLVED.clear()
    calls = {"n": 0}
    original = workdir_core._usable

    def counting(path):
        calls["n"] += 1
        return original(path)

    workdir_core._usable = counting
    try:
        for _ in range(5):
            workdir_core.resolve(root)
        # แตะดิสก์ครั้งเดียว ไม่ใช่ทุกรีเควสต์
        assert calls["n"] == 1
    finally:
        workdir_core._usable = original


def test_work_created_while_the_drive_was_away_comes_back(tmp_path: Path):
    """ไดรฟ์หลุด → กรอกงานลงที่เก็บเริ่มต้น → ไดรฟ์กลับมา งานนั้นต้องไม่หายไปจากลิสต์"""
    root = tmp_path / "user"
    root.mkdir()
    dest = tmp_path / "ไดรฟ์เครือข่าย"
    workdir_core.set_work_dir(root, str(dest))
    (dest / "sheets" / "ใบเก่า.json").write_text("{}", encoding="utf-8")

    # ไดรฟ์หลุด
    original = workdir_core._usable
    workdir_core._usable = lambda path: False
    workdir_core._RESOLVED.clear()
    try:
        assert workdir_core.resolve(root) == root
        # ครูยังกรอกงานต่อ — ลงที่เก็บเริ่มต้นแทน
        (root / "sheets").mkdir(parents=True, exist_ok=True)
        (root / "sheets" / "ใบตอนไดรฟ์หลุด.json").write_text("{}", encoding="utf-8")
        (root / "output").mkdir(parents=True, exist_ok=True)
        (root / "output" / "พิมพ์ตอนไดรฟ์หลุด.pdf").write_bytes(b"%PDF-x")
    finally:
        workdir_core._usable = original

    # ไดรฟ์กลับมา
    workdir_core._RESOLVED.clear()
    assert workdir_core.resolve(root) == dest.resolve()

    names = {p.name for p in (dest / "sheets").glob("*.json")}
    assert names == {"ใบเก่า.json", "ใบตอนไดรฟ์หลุด.json"}, names
    assert (dest / "output" / "พิมพ์ตอนไดรฟ์หลุด.pdf").is_file()
    # ไม่ทิ้งสำเนาค้างไว้ที่เก็บเริ่มต้น
    assert not list((root / "sheets").glob("*.json"))


def test_reclaim_does_not_run_when_there_is_nothing_to_move(tmp_path: Path):
    root = tmp_path / "user"
    root.mkdir()
    dest = tmp_path / "dest"
    workdir_core.set_work_dir(root, str(dest))
    (dest / "sheets" / "ก.json").write_text("ของจริง", encoding="utf-8")

    for _ in range(3):
        workdir_core._RESOLVED.clear()
        assert workdir_core.resolve(root) == dest.resolve()
    assert (dest / "sheets" / "ก.json").read_text(encoding="utf-8") == "ของจริง"


def test_reclaim_never_overwrites_a_file_at_the_destination(tmp_path: Path):
    root = tmp_path / "user"
    root.mkdir()
    dest = tmp_path / "dest"
    workdir_core.set_work_dir(root, str(dest))
    (dest / "sheets" / "ชนกัน.json").write_text("ของที่ปลายทาง", encoding="utf-8")
    (root / "sheets").mkdir(parents=True, exist_ok=True)
    (root / "sheets" / "ชนกัน.json").write_text("ของที่ตกค้าง", encoding="utf-8")

    workdir_core._RESOLVED.clear()
    workdir_core.resolve(root)
    assert (dest / "sheets" / "ชนกัน.json").read_text(encoding="utf-8") == "ของที่ปลายทาง"
