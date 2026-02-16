from __future__ import annotations

from dux.config.schema import AppConfig, PatternRule
from dux.models.enums import InsightCategory, NodeKind
from dux.models.insight import Insight, InsightBundle
from dux.models.scan import ScanNode
from dux.services.insights import _heap_push, filter_insights, generate_insights
from dux.services.tree import LEAF_CHILDREN


def _dir(path: str, name: str, children: list[ScanNode] | None = None, du: int = 0) -> ScanNode:
    return ScanNode(
        path=path, name=name, kind=NodeKind.DIRECTORY, size_bytes=du, disk_usage=du, children=children or []
    )


def _file(path: str, name: str, du: int = 0) -> ScanNode:
    return ScanNode(path=path, name=name, kind=NodeKind.FILE, size_bytes=du, disk_usage=du, children=LEAF_CHILDREN)


def _insight(path: str, du: int) -> Insight:
    return Insight(path=path, size_bytes=du, category=InsightCategory.TEMP, summary="test", disk_usage=du)


class TestHeapPush:
    def test_dedup_lower_usage_skipped(self) -> None:
        heap: list[tuple[int, str, Insight]] = []
        seen: dict[str, int] = {}
        i1 = _insight("/a", 100)
        i2 = _insight("/a", 50)
        _heap_push(heap, seen, i1, 10)
        _heap_push(heap, seen, i2, 10)
        # Only one entry with the higher usage
        assert seen["/a"] == 100
        assert len(heap) == 1

    def test_dedup_higher_usage_replaces(self) -> None:
        heap: list[tuple[int, str, Insight]] = []
        seen: dict[str, int] = {}
        i1 = _insight("/a", 50)
        i2 = _insight("/a", 100)
        _heap_push(heap, seen, i1, 10)
        _heap_push(heap, seen, i2, 10)
        assert seen["/a"] == 100
        # Both may be in heap (lazy eviction), but seen tracks the latest
        assert len(heap) == 2

    def test_replace_on_full_heap(self) -> None:
        heap: list[tuple[int, str, Insight]] = []
        seen: dict[str, int] = {}
        # Fill heap of size 2
        _heap_push(heap, seen, _insight("/a", 10), 2)
        _heap_push(heap, seen, _insight("/b", 20), 2)
        assert len(heap) == 2
        # Push larger → evicts smallest
        _heap_push(heap, seen, _insight("/c", 30), 2)
        assert len(heap) == 2
        paths = {e[1] for e in heap}
        assert "/c" in paths

    def test_skip_when_too_small_for_full_heap(self) -> None:
        heap: list[tuple[int, str, Insight]] = []
        seen: dict[str, int] = {}
        _heap_push(heap, seen, _insight("/a", 100), 2)
        _heap_push(heap, seen, _insight("/b", 200), 2)
        # Smaller than min in heap → not added to heap
        _heap_push(heap, seen, _insight("/c", 5), 2)
        assert len(heap) == 2
        # seen is always updated, but heap didn't grow
        paths_in_heap = {e[1] for e in heap}
        assert "/c" not in paths_in_heap


class TestGenerateInsights:
    def test_descendant_skip(self) -> None:
        """Children under a matched temp dir are not individually matched."""
        inner_file = _file("/r/tmp/inner.log", "inner.log", du=50)
        tmp_dir = _dir("/r/tmp", "tmp", [inner_file], du=50)
        root = _dir("/r", "root", [tmp_dir], du=50)
        config = AppConfig(
            temp_patterns=[PatternRule("tmp", "**/tmp/**", InsightCategory.TEMP)],
            max_insights_per_category=100,
        )
        bundle = generate_insights(root, config)
        temp_paths = {i.path for i in bundle.insights if i.category is InsightCategory.TEMP}
        assert "/r/tmp" in temp_paths
        # inner.log should NOT be individually matched (descendant skip)
        assert "/r/tmp/inner.log" not in temp_paths

    def test_stop_recursion(self) -> None:
        """Dirs with stop_recursion skip child enumeration entirely."""
        inner = _file("/r/node_modules/pkg/a.js", "a.js", du=10)
        pkg = _dir("/r/node_modules/pkg", "pkg", [inner], du=10)
        nm = _dir("/r/node_modules", "node_modules", [pkg], du=10)
        root = _dir("/r", "root", [nm], du=10)
        config = AppConfig(
            build_artifact_patterns=[
                PatternRule("nm", "**/node_modules/**", InsightCategory.BUILD_ARTIFACT, stop_recursion=True),
            ],
            max_insights_per_category=100,
        )
        bundle = generate_insights(root, config)
        matched_paths = {i.path for i in bundle.insights}
        assert "/r/node_modules" in matched_paths
        # Children should not be matched because stop_recursion skips the dir
        assert "/r/node_modules/pkg" not in matched_paths


class TestFilterInsights:
    def test_basic_filter(self) -> None:
        insights = [
            Insight("/a", 10, InsightCategory.TEMP, "t", disk_usage=10),
            Insight("/b", 20, InsightCategory.CACHE, "c", disk_usage=20),
            Insight("/c", 30, InsightCategory.BUILD_ARTIFACT, "b", disk_usage=30),
        ]
        bundle = InsightBundle(insights=insights, by_category={})
        result = filter_insights(bundle, {InsightCategory.TEMP})
        assert len(result) == 1
        assert result[0].path == "/a"

    def test_empty_categories(self) -> None:
        insights = [Insight("/a", 10, InsightCategory.TEMP, "t", disk_usage=10)]
        bundle = InsightBundle(insights=insights, by_category={})
        result = filter_insights(bundle, set())
        assert len(result) == 0

    def test_all_match(self) -> None:
        insights = [
            Insight("/a", 10, InsightCategory.TEMP, "t", disk_usage=10),
            Insight("/b", 20, InsightCategory.TEMP, "t", disk_usage=20),
        ]
        bundle = InsightBundle(insights=insights, by_category={})
        result = filter_insights(bundle, {InsightCategory.TEMP})
        assert len(result) == 2
