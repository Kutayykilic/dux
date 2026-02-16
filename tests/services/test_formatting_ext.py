from __future__ import annotations

from dux.services.formatting import relative_bar


class TestRelativeBar:
    def test_normal_mid_range(self) -> None:
        result = relative_bar(50, 100, width=10)
        assert result == "█" * 5 + "░" * 5

    def test_full_bar(self) -> None:
        result = relative_bar(100, 100, width=10)
        assert result == "█" * 10

    def test_empty_bar(self) -> None:
        result = relative_bar(0, 100, width=10)
        assert result == "░" * 10

    def test_clamped_above_one(self) -> None:
        result = relative_bar(200, 100, width=10)
        assert result == "█" * 10

    def test_total_zero_returns_empty(self) -> None:
        assert relative_bar(50, 0, width=10) == ""

    def test_width_zero_returns_empty(self) -> None:
        assert relative_bar(50, 100, width=0) == ""
