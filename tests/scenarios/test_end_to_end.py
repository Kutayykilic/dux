from __future__ import annotations

from dux.config.defaults import default_config
from dux.config.schema import AppConfig, PatternRule, from_dict
from dux.models.enums import ApplyTo, InsightCategory, NodeKind
from dux.models.scan import ScanNode, ScanOptions
from dux.scan.python_scanner import PythonScanner
from dux.services.insights import generate_insights
from dux.services.tree import LEAF_CHILDREN, finalize_sizes
from tests.fs_mock import MemoryFileSystem


def _dir(path: str, name: str, children: list[ScanNode] | None = None, du: int = 0) -> ScanNode:
    return ScanNode(
        path=path, name=name, kind=NodeKind.DIRECTORY, size_bytes=du, disk_usage=du, children=children or []
    )


def _file(path: str, name: str, du: int = 0) -> ScanNode:
    return ScanNode(path=path, name=name, kind=NodeKind.FILE, size_bytes=du, disk_usage=du, children=LEAF_CHILDREN)


class TestFullPipeline:
    def test_scan_then_insights(self) -> None:
        fs = MemoryFileSystem()
        fs.add_dir("/project")
        fs.add_file("/project/src/main.py", size=100, disk_usage=100)
        fs.add_file("/project/tmp/trace.log", size=500, disk_usage=500)
        fs.add_file("/project/.cache/pip/some.whl", size=200, disk_usage=200)

        scanner = PythonScanner(workers=1, fs=fs)
        result = scanner.scan("/project", ScanOptions())
        snapshot = result.unwrap()
        config = default_config()
        bundle = generate_insights(snapshot.root, config)

        categories = {i.category for i in bundle.insights}
        assert InsightCategory.TEMP in categories or InsightCategory.CACHE in categories


class TestMixedCategories:
    def test_temp_cache_build_in_one_tree(self) -> None:
        tmp_file = _file("/r/tmp/x.log", "x.log", du=100)
        tmp_dir = _dir("/r/tmp", "tmp", [tmp_file], du=100)
        cache_file = _file("/r/.cache/pip/a.whl", "a.whl", du=200)
        pip_dir = _dir("/r/.cache/pip", "pip", [cache_file], du=200)
        cache_dir = _dir("/r/.cache", ".cache", [pip_dir], du=200)
        nm_file = _file("/r/node_modules/pkg/index.js", "index.js", du=50)
        pkg = _dir("/r/node_modules/pkg", "pkg", [nm_file], du=50)
        nm = _dir("/r/node_modules", "node_modules", [pkg], du=50)
        root = _dir("/r", "root", [tmp_dir, cache_dir, nm], du=350)
        finalize_sizes(root)

        config = default_config()
        bundle = generate_insights(root, config)
        categories = {i.category for i in bundle.insights}
        assert InsightCategory.TEMP in categories
        assert InsightCategory.CACHE in categories
        assert InsightCategory.BUILD_ARTIFACT in categories


class TestCaseInsensitive:
    def test_mixed_case_paths_match(self) -> None:
        ds = _file("/r/DIR/.DS_STORE", ".DS_STORE", du=10)
        d = _dir("/r/DIR", "DIR", [ds], du=10)
        root = _dir("/r", "root", [d], du=10)
        finalize_sizes(root)
        config = default_config()
        bundle = generate_insights(root, config)
        matched = {i.path for i in bundle.insights}
        assert "/r/DIR/.DS_STORE" in matched


class TestAdditionalPaths:
    def test_additional_cache_path(self) -> None:
        cache_file = _file("/home/.mycache/data", "data", du=300)
        cache_dir = _dir("/home/.mycache", ".mycache", [cache_file], du=300)
        root = _dir("/home", "home", [cache_dir], du=300)
        finalize_sizes(root)

        config = AppConfig(
            additional_cache_paths=["/home/.mycache"],
            max_insights_per_category=100,
        )
        bundle = generate_insights(root, config)
        cache_paths = {i.path for i in bundle.insights if i.category is InsightCategory.CACHE}
        assert "/home/.mycache" in cache_paths


class TestStopRecursion:
    def test_node_modules_stops_descent(self) -> None:
        inner = _file("/r/node_modules/pkg/a.js", "a.js", du=10)
        pkg = _dir("/r/node_modules/pkg", "pkg", [inner], du=10)
        nm = _dir("/r/node_modules", "node_modules", [pkg], du=10)
        root = _dir("/r", "root", [nm], du=10)
        finalize_sizes(root)

        config = default_config()
        bundle = generate_insights(root, config)
        matched = {i.path for i in bundle.insights}
        assert "/r/node_modules" in matched
        # Children not individually matched due to stop_recursion
        assert "/r/node_modules/pkg" not in matched
        assert "/r/node_modules/pkg/a.js" not in matched


class TestConfigRoundTrip:
    def test_default_to_dict_from_dict(self) -> None:
        original = default_config()
        d = original.to_dict()
        restored = from_dict(d, AppConfig())
        assert restored.scan_workers == original.scan_workers
        assert restored.top_count == original.top_count
        assert restored.page_size == original.page_size
        assert restored.max_depth == original.max_depth
        assert len(restored.temp_patterns) == len(original.temp_patterns)
        assert len(restored.cache_patterns) == len(original.cache_patterns)
        assert len(restored.build_artifact_patterns) == len(original.build_artifact_patterns)


class TestEmptyTree:
    def test_root_with_no_children(self) -> None:
        root = _dir("/r", "root", [], du=0)
        config = default_config()
        bundle = generate_insights(root, config)
        assert len(bundle.insights) == 0


class TestHeapEviction:
    def test_only_top_k_kept(self) -> None:
        children = [_file(f"/r/tmp/f{i}.log", f"f{i}.log", du=i * 10) for i in range(20)]
        tmp = _dir("/r/tmp", "tmp", children, du=sum(i * 10 for i in range(20)))
        root = _dir("/r", "root", [tmp], du=tmp.disk_usage)
        finalize_sizes(root)

        config = AppConfig(
            temp_patterns=[PatternRule("logs", "**/*.log", InsightCategory.TEMP, apply_to=ApplyTo.FILE)],
            max_insights_per_category=5,
        )
        bundle = generate_insights(root, config)
        temp_insights = [i for i in bundle.insights if i.category is InsightCategory.TEMP]
        # Should be at most 5 (max_insights_per_category)
        assert len(temp_insights) <= 5
        # The kept ones should be the largest
        if temp_insights:
            min_kept = min(i.disk_usage for i in temp_insights)
            # Files with du=0 through du=140 (range 0..14 * 10 for the 15 smallest)
            # The top 5 should be du=190,180,170,160,150
            assert min_kept >= 100  # at least bigger than the bottom 10
