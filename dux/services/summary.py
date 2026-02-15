from __future__ import annotations

from rich.console import Console
from rich.table import Table

from dux.models.enums import InsightCategory, NodeKind
from dux.models.insight import Insight, InsightBundle
from dux.models.scan import ScanNode, ScanStats
from dux.services.formatting import format_bytes
from dux.services.insights import filter_insights
from dux.services.tree import top_nodes


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
    stats: ScanStats,
    root_prefix: str,
) -> None:
    table = Table(title="Top Level Summary", header_style="bold cyan")
    table.add_column("Path")
    table.add_column("Type", justify="center")
    table.add_column("Size", justify="right")

    for child in sorted(root.children, key=lambda n: n.size_bytes, reverse=True):
        table.add_row(
            _trim(child.path, root_prefix),
            "DIR" if child.kind is NodeKind.DIRECTORY else "FILE",
            format_bytes(child.size_bytes),
        )

    table.add_section()
    table.add_row("[bold]Total[/bold]", "", f"[bold]{format_bytes(root.size_bytes)}[/bold]")
    table.add_section()
    table.add_row(f"[bold]{stats.directories:,}[/bold] dirs", "", "")
    table.add_row(f"[bold]{stats.files:,}[/bold] files", "", "")

    console.print(table)


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
