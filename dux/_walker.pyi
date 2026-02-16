from dux.models.enums import NodeKind
from dux.models.scan import ScanNode

def scan_dir_nodes(
    path: str,
    parent: ScanNode,
    leaf: list[ScanNode],
    kind_dir: NodeKind,
    kind_file: NodeKind,
    scan_node_cls: type[ScanNode],
) -> tuple[list[ScanNode], int, int, int]: ...
def scan_dir_bulk_nodes(
    path: str,
    parent: ScanNode,
    leaf: list[ScanNode],
    kind_dir: NodeKind,
    kind_file: NodeKind,
    scan_node_cls: type[ScanNode],
) -> tuple[list[ScanNode], int, int, int]: ...
