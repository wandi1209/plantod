"""Rich terminal output helpers — status-driven, short (PRD 22)."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

console = Console()

_STYLES = {
    "INFO": "cyan",
    "OK": "green",
    "WARN": "yellow",
    "ERROR": "red",
}


def _emit(level: str, message: str) -> None:
    style = _STYLES.get(level, "white")
    console.print(f"[{style}]\\[{level}][/{style}] {message}")


def info(message: str) -> None:
    _emit("INFO", message)


def ok(message: str) -> None:
    _emit("OK", message)


def warn(message: str) -> None:
    _emit("WARN", message)


def error(message: str) -> None:
    _emit("ERROR", message)


def tasks_table(tasks: list) -> Table:
    table = Table(title="Tasks")
    table.add_column("ID", style="bold")
    table.add_column("Title")
    table.add_column("Risk")
    table.add_column("Status")
    table.add_column("Depends")
    for t in tasks:
        table.add_row(
            t.id,
            t.title,
            t.risk_level.value,
            t.status.value,
            ", ".join(t.depends_on) or "-",
        )
    return table
