from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from dux.models.enums import InsightCategory, NodeKind
from dux.models.insight import Insight, InsightBundle
from dux.models.scan import ScanNode, ScanStats
from dux.services.formatting import format_bytes
from dux.services.insights import filter_insights
from dux.services.tree import top_nodes


def stats_panel(root: ScanNode, stats: ScanStats) -> Panel:
    body = (
        f"Files: [bold]{stats.files}[/bold]\n"
        f"Directories: [bold]{stats.directories}[/bold]\n"
        f"Total Size: [bold]{format_bytes(root.size_bytes)}[/bold]\n"
        f"Access Errors: [bold]{stats.access_errors}[/bold]"
    )
    return Panel(body, title="Scan Summary", border_style="blue")


def _trim(path: str, root_prefix: str) -> str:
    return path[len(root_prefix) :] if path.startswith(root_prefix) else path


def _insights_table(title: str, insights: list[Insight], top_n: int, root_prefix: str) -> Table:
    table = Table(title=title, header_style="bold yellow")
    table.add_column("Path")
    table.add_column("Type", justify="center")
    table.add_column("Category")
    table.add_column("Size", justify="right")
    for item in insights[:top_n]:
        table.add_row(
            _trim(item.path, root_prefix),
            "DIR" if item.kind is NodeKind.DIRECTORY else "FILE",
            item.category.value,
            format_bytes(item.size_bytes),
        )
    return table


def _top_nodes_table(title: str, root: ScanNode, top_n: int, kind: NodeKind, root_prefix: str) -> Table:
    table = Table(title=title, header_style="bold yellow")
    table.add_column("Path")
    table.add_column("Size", justify="right")
    for node in top_nodes(root, top_n, kind):
        table.add_row(_trim(node.path, root_prefix), format_bytes(node.size_bytes))
    return table


def render_summary(
    console: Console,
    root: ScanNode,
    root_prefix: str,
) -> None:
    top_table = Table(title="Top Level Files/Directories", header_style="bold cyan")
    top_table.add_column("Path")
    top_table.add_column("Type", justify="center")
    top_table.add_column("Size", justify="right")

    for child in sorted(root.children, key=lambda n: n.size_bytes, reverse=True):
        top_table.add_row(
            _trim(child.path, root_prefix),
            "DIR" if child.kind is NodeKind.DIRECTORY else "FILE",
            format_bytes(child.size_bytes),
        )
    console.print(top_table)


def render_focused_summary(
    console: Console,
    root: ScanNode,
    bundle: InsightBundle,
    top_n: int,
    root_prefix: str,
    *,
    top_temp: bool = False,
    top_cache: bool = False,
    top_dirs: bool = False,
    top_files: bool = False,
) -> None:
    if top_temp:
        insights = filter_insights(bundle, {InsightCategory.TEMP, InsightCategory.BUILD_ARTIFACT})
        console.print(_insights_table("Largest Temporary Files/Directories", insights, top_n, root_prefix))
    if top_cache:
        insights = filter_insights(bundle, {InsightCategory.CACHE})
        console.print(_insights_table("Largest Cache Files/Directories", insights, top_n, root_prefix))

    if top_dirs:
        console.print(_top_nodes_table("Largest Directories", root, top_n, NodeKind.DIRECTORY, root_prefix))
    if top_files:
        console.print(_top_nodes_table("Largest Files", root, top_n, NodeKind.FILE, root_prefix))
