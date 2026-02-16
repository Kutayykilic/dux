from __future__ import annotations

from typing import override

from dux.models.enums import NodeKind
from dux.models.scan import ScanErrorCode, ScanNode, ScanOptions
from dux.scan._base import ThreadedScannerBase, resolve_root
from dux.services.tree import LEAF_CHILDREN
from tests.fs_mock import MemoryFileSystem


class TestResolveRoot:
    def test_stat_oserror_returns_root_stat_failed(self) -> None:
        class _FailStatFS(MemoryFileSystem):
            @override
            def stat(self, path: str) -> None:  # type: ignore[override]
                raise OSError("Permission denied")

        fs = _FailStatFS()
        fs.add_dir("/root")
        result = resolve_root("/root", fs)
        assert not isinstance(result, str)
        assert result.code is ScanErrorCode.ROOT_STAT_FAILED

    def test_file_path_returns_not_directory(self) -> None:
        fs = MemoryFileSystem()
        fs.add_file("/root/file.txt", size=10)
        result = resolve_root("/root/file.txt", fs)
        assert not isinstance(result, str)
        assert result.code is ScanErrorCode.NOT_DIRECTORY

    def test_valid_dir_returns_path(self) -> None:
        fs = MemoryFileSystem()
        fs.add_dir("/root")
        result = resolve_root("/root", fs)
        assert isinstance(result, str)
        assert result == "/root"


class _TestableScanner(ThreadedScannerBase):
    """Minimal subclass for testing base class behavior."""

    def __init__(self, fs: MemoryFileSystem, fail_on: str | None = None) -> None:
        super().__init__(workers=1, fs=fs)
        self._fail_on = fail_on

    @override
    def _scan_dir(self, parent: ScanNode, path: str) -> tuple[list[ScanNode], int, int, int]:
        if self._fail_on and path == self._fail_on:
            raise OSError("Simulated failure")
        dir_children: list[ScanNode] = []
        errors = 0
        files = 0
        dirs = 0
        for entry in self._fs.scandir(path):
            st = entry.stat
            if st is None:
                errors += 1
                continue
            if st.is_dir:
                node = ScanNode(
                    path=entry.path,
                    name=entry.name,
                    kind=NodeKind.DIRECTORY,
                    size_bytes=0,
                    disk_usage=0,
                    children=[],
                )
                parent.children.append(node)
                dir_children.append(node)
                dirs += 1
            else:
                node = ScanNode(
                    path=entry.path,
                    name=entry.name,
                    kind=NodeKind.FILE,
                    size_bytes=st.size,
                    disk_usage=st.disk_usage,
                    children=LEAF_CHILDREN,
                )
                parent.children.append(node)
                files += 1
        return dir_children, files, dirs, errors


class TestScanDirError:
    def test_scan_dir_exception_increments_errors(self) -> None:
        fs = MemoryFileSystem()
        fs.add_dir("/root")
        fs.add_dir("/root/sub")
        fs.add_file("/root/sub/a.txt", size=10)
        scanner = _TestableScanner(fs, fail_on="/root/sub")
        result = scanner.scan("/root", ScanOptions())
        snapshot = result.unwrap()
        assert snapshot.stats.access_errors >= 1
