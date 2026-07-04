"""Chat-like interactive REPL — bare `plantod` (PRD 11, 12.B, FR-03)."""

from __future__ import annotations

from . import orchestrator, ui
from .repo import scan_repo
from .state import StateManager

_BANNER = "PLANTOD — Plan, Task, Orchestrate, Deliver. Type a request, or /help."
_HELP = (
    "/help            show this help\n"
    "/status          board summary\n"
    "/tasks           list tasks\n"
    "/review <RID>    final review a requirement\n"
    "/quit            exit"
)


def repl() -> None:
    state = StateManager(".")
    if not state.is_initialized():
        ui.warn("Not initialized. Run `plantod init` first.")
        return

    ui.console.print(_BANNER)
    repo = scan_repo(state.root)
    while True:
        try:
            line = input("plantod> ").strip()
        except (EOFError, KeyboardInterrupt):
            ui.console.print()
            break
        if not line:
            continue
        if line in ("/quit", "/exit"):
            break
        if line == "/help":
            ui.console.print(_HELP)
            continue
        if line == "/status":
            _status(state)
            continue
        if line == "/tasks":
            if state.board.tasks:
                ui.console.print(ui.tasks_table(list(state.board.tasks.values())))
            else:
                ui.info("No tasks yet.")
            continue
        if line.startswith("/review"):
            parts = line.split()
            if len(parts) < 2:
                ui.error("Usage: /review <requirement-id>")
                continue
            from . import reviewer

            try:
                r = reviewer.review_requirement(state, parts[1], repo)
                ui.ok(f"Review ({r.verdict}) written.")
            except KeyError as e:
                ui.error(str(e))
            continue
        # natural-language request -> default flow
        orchestrator.run_request(
            state, line, repo=repo, approval=_confirm, auto_review=False
        )


def _confirm(task) -> bool:
    ans = input(f"Approve {task.id} ({task.risk_level.value}) '{task.title}'? [y/N] ").strip().lower()
    return ans in ("y", "yes")


def _status(state: StateManager) -> None:
    counts: dict[str, int] = {}
    for t in state.board.tasks.values():
        counts[t.status.value] = counts.get(t.status.value, 0) + 1
    ui.info(
        f"Requirements: {len(state.board.requirements)} | "
        f"Tasks: {len(state.board.tasks)} | " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
    )
