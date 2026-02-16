from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from dux.services.fs import OsFileSystem


class TestOsFileSystem:
    def test_scandir_normal(self, tmp_path: Path) -> None:
        (tmp_path / "hello.txt").write_text("hi")
        fs = OsFileSystem()
        entries = list(fs.scandir(str(tmp_path)))
        assert len(entries) == 1
        assert entries[0].name == "hello.txt"
        assert entries[0].stat is not None
        assert entries[0].stat.size > 0
        assert entries[0].stat.is_dir is False

    def test_scandir_stat_failure(self, tmp_path: Path) -> None:
        (tmp_path / "bad.txt").write_text("x")
        fs = OsFileSystem()

        original_scandir = os.scandir

        class _FakeEntry:
            def __init__(self, real_entry: os.DirEntry[str]) -> None:
                self.path = real_entry.path
                self.name = real_entry.name

            def stat(self, *, follow_symlinks: bool = True) -> None:
                raise OSError("perm denied")

        def _patched_scandir(path: str):  # type: ignore[no-untyped-def]
            cm = original_scandir(path)
            entries = list(cm)
            cm.close()

            class _FakeCtx:
                def __enter__(self) -> list[_FakeEntry]:
                    return [_FakeEntry(e) for e in entries]

                def __exit__(self, *a: object) -> None:
                    pass

            return _FakeCtx()

        with patch("dux.services.fs.os.scandir", side_effect=_patched_scandir):
            results = list(fs.scandir(str(tmp_path)))
        assert len(results) == 1
        assert results[0].stat is None

    def test_read_text(self, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("hello world")
        fs = OsFileSystem()
        assert fs.read_text(str(f)) == "hello world"

    def test_stat_returns_stat_result(self, tmp_path: Path) -> None:
        f = tmp_path / "x.txt"
        f.write_text("abc")
        fs = OsFileSystem()
        sr = fs.stat(str(f))
        assert sr.size == 3
        assert sr.is_dir is False
        assert sr.disk_usage >= 0
