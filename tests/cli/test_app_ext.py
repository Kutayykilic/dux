from __future__ import annotations

import time

from rich.panel import Panel

from dux.cli.app import _ScanProgress, _render_scan_panel, _truncate_path


class TestTruncatePath:
    def test_short_path_unchanged(self) -> None:
        assert _truncate_path("/short/path", max_width=110) == "/short/path"

    def test_exact_width_unchanged(self) -> None:
        path = "x" * 110
        assert _truncate_path(path, max_width=110) == path

    def test_long_path_truncated(self) -> None:
        path = "x" * 200
        result = _truncate_path(path, max_width=50)
        assert result.startswith("...")
        assert len(result) == 50

    def test_truncated_keeps_suffix(self) -> None:
        path = "/very/long/path/to/some/deeply/nested/file.txt"
        result = _truncate_path(path, max_width=20)
        assert result.endswith("file.txt")


class TestRenderScanPanel:
    def test_returns_panel(self) -> None:
        progress = _ScanProgress(
            current_path="/some/path",
            files=42,
            directories=10,
            start_time=time.perf_counter() - 1.0,
        )
        result = _render_scan_panel(progress, workers=4, phase="Scanning...")
        assert isinstance(result, Panel)
