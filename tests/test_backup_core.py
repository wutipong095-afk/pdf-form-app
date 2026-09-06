import io
import json
import zipfile
from pathlib import Path

import pytest
import backup_core


def archive(corrupt=False):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_STORED) as zf:
        zf.writestr("meta.json", json.dumps({"kind": "pdf-form-marker-backup"}))
        zf.writestr("user/uploads/new.pdf", b"UNIQUE_PDF_PAYLOAD")
    raw = bytearray(buf.getvalue())
    if corrupt:
        raw[raw.index(b"UNIQUE_PDF_PAYLOAD")] = 88
    return io.BytesIO(raw)


def test_corrupt_replace_preserves_existing_work(tmp_path):
    old = tmp_path / "uploads" / "old.pdf"
    old.parent.mkdir()
    old.write_bytes(b"original")
    with pytest.raises(zipfile.BadZipFile):
        backup_core.restore_backup(archive(True), user_root=tmp_path, data_dir=tmp_path, mode="replace")
    assert old.read_bytes() == b"original"
    assert not (old.parent / "new.pdf").exists()


def test_replace_write_failure_rolls_back(tmp_path, monkeypatch):
    old = tmp_path / "uploads" / "old.pdf"
    old.parent.mkdir()
    old.write_bytes(b"original")
    real_write = Path.write_bytes
    def fail_new(path, content):
        if path.name == "new.pdf":
            real_write(path, b"partial")
            raise OSError("disk full")
        return real_write(path, content)
    monkeypatch.setattr(Path, "write_bytes", fail_new)
    with pytest.raises(OSError):
        backup_core.restore_backup(archive(), user_root=tmp_path, data_dir=tmp_path, mode="replace")
    assert old.read_bytes() == b"original"
    assert not (old.parent / "new.pdf").exists()


def test_replace_commits_complete_archive(tmp_path):
    old = tmp_path / "uploads" / "old.pdf"
    old.parent.mkdir()
    old.write_bytes(b"original")
    backup_core.restore_backup(archive(), user_root=tmp_path, data_dir=tmp_path, mode="replace")
    assert not old.exists()
    assert (old.parent / "new.pdf").read_bytes() == b"UNIQUE_PDF_PAYLOAD"


def test_merge_keeps_existing_files_and_restores_library_metadata(tmp_path):
    library = tmp_path / "library"
    library.mkdir()
    old = tmp_path / "uploads" / "new.pdf"
    old.parent.mkdir()
    old.write_bytes(b"keep me")
    buf = archive()
    with zipfile.ZipFile(buf, "a") as zf:
        zf.writestr("library/library.json", json.dumps({"root": str(library)}))
        zf.writestr("library/pdfmarker/settings.json", b"{}")
    backup_core.restore_backup(buf, user_root=tmp_path, data_dir=tmp_path)
    assert old.read_bytes() == b"keep me"
    assert (library / ".pdfmarker" / "settings.json").read_bytes() == b"{}"
