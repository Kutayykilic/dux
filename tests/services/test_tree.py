from __future__ import annotations

from dux.models.enums import NodeKind
from dux.models.scan import ScanNode
from dux.services.tree import LEAF_CHILDREN, iter_nodes, top_nodes


def _dir(path: str, name: str, children: list[ScanNode] | None = None, du: int = 0) -> ScanNode:
    return ScanNode(
        path=path, name=name, kind=NodeKind.DIRECTORY, size_bytes=du, disk_usage=du, children=children or []
    )


def _file(path: str, name: str, du: int = 0) -> ScanNode:
    return ScanNode(path=path, name=name, kind=NodeKind.FILE, size_bytes=du, disk_usage=du, children=LEAF_CHILDREN)


class TestIterNodes:
    def test_single_root(self) -> None:
        root = _dir("/root", "root")
        assert list(iter_nodes(root)) == [root]

    def test_nested_tree(self) -> None:
        f1 = _file("/root/a.txt", "a.txt", du=10)
        f2 = _file("/root/sub/b.txt", "b.txt", du=20)
        sub = _dir("/root/sub", "sub", [f2], du=20)
        root = _dir("/root", "root", [f1, sub], du=30)
        paths = [n.path for n in iter_nodes(root)]
        assert "/root" in paths
        assert "/root/a.txt" in paths
        assert "/root/sub" in paths
        assert "/root/sub/b.txt" in paths
        assert len(paths) == 4


class TestTopNodes:
    def test_kind_none_returns_all(self) -> None:
        f1 = _file("/r/a", "a", du=10)
        f2 = _file("/r/b", "b", du=20)
        sub = _dir("/r/sub", "sub", [f2], du=20)
        root = _dir("/r", "root", [f1, sub], du=30)
        result = top_nodes(root, 10, kind=None)
        # root excluded, all others present
        assert len(result) == 3
        assert result[0].path in {"/r/sub", "/r/b"}

    def test_kind_file(self) -> None:
        f1 = _file("/r/a", "a", du=10)
        f2 = _file("/r/b", "b", du=20)
        sub = _dir("/r/sub", "sub", [], du=5)
        root = _dir("/r", "root", [f1, f2, sub], du=35)
        result = top_nodes(root, 10, kind=NodeKind.FILE)
        assert all(n.kind is NodeKind.FILE for n in result)
        assert len(result) == 2
        assert result[0].disk_usage >= result[1].disk_usage

    def test_kind_directory(self) -> None:
        f1 = _file("/r/a", "a", du=10)
        sub = _dir("/r/sub", "sub", [], du=5)
        root = _dir("/r", "root", [f1, sub], du=15)
        result = top_nodes(root, 10, kind=NodeKind.DIRECTORY)
        assert len(result) == 1
        assert result[0].path == "/r/sub"

    def test_n_greater_than_count(self) -> None:
        f1 = _file("/r/a", "a", du=10)
        root = _dir("/r", "root", [f1], du=10)
        result = top_nodes(root, 100, kind=None)
        assert len(result) == 1

    def test_root_excluded(self) -> None:
        root = _dir("/r", "root", [], du=100)
        result = top_nodes(root, 10, kind=None)
        assert len(result) == 0
