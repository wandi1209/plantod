"""PLANTOD command-line interface (PRD 16)."""

from __future__ import annotations

from pathlib import Path

import typer

from . import orchestrator, reviewer, ui
from .repo import scan_repo
from .schemas import TaskEvent
from .state import StateManager

app = typer.Typer(
    help="PLANTOD — planning-first AI coding orchestrator.",
    no_args_is_help=False,
    add_completion=False,
)


def _state() -> StateManager:
    return StateManager(".")


def _require_init(state: StateManager) -> None:
    if not state.is_initialized():
        ui.error("Not initialized. Run `plantod init` first.")
        raise typer.Exit(1)


@app.command()
def init() -> None:
    """Detect repo and scaffold .plantod/ (PRD 12.A, FR-01/02)."""
    repo = scan_repo(".")
    if not repo.is_git:
        ui.warn("Current directory is not a git repo. Proceeding anyway.")
    state = StateManager(".")
    if state.is_initialized():
        ui.warn(f"Already initialized at {state.artifact_dir}")
        return
    state.initialize()
    ui.ok(f"Initialized {state.artifact_dir}")
    ui.info(f"Detected test command: {repo.test_command or 'none'}")


@app.command()
def status() -> None:
    """Show board summary and current session (FR-06)."""
    state = _state()
    _require_init(state)
    counts: dict[str, int] = {}
    for t in state.board.tasks.values():
        counts[t.status.value] = counts.get(t.status.value, 0) + 1
    ui.info(f"Requirements: {len(state.board.requirements)} | Plans: {len(state.board.plans)} | Tasks: {len(state.board.tasks)}")
    for status_name, n in sorted(counts.items()):
        ui.info(f"  {status_name}: {n}")
    if state.session.current_requirement_id:
        ui.info(f"Current requirement: {state.session.current_requirement_id}")
    nxt = state.next_runnable()
    if nxt:
        ui.info(f"Next runnable: {nxt.id}")


@app.command()
def plan(
    request: str = typer.Argument(..., help="Natural-language request"),
    review: bool = typer.Option(False, "--review", help="Run final review after tasks"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Approve all gated tasks"),
) -> None:
    """Plan a request, break into tasks, and run the default flow (FR-04/05)."""
    state = _state()
    _require_init(state)
    approval = (lambda _t: True) if yes else _prompt_approval
    orchestrator.run_request(state, request, approval=approval, auto_review=review)


@app.command()
def tasks() -> None:
    """List tasks with status (FR-06)."""
    state = _state()
    _require_init(state)
    if not state.board.tasks:
        ui.info("No tasks yet. Run `plantod plan \"<request>\"`.")
        return
    ui.console.print(ui.tasks_table(list(state.board.tasks.values())))


@app.command()
def next() -> None:
    """Show the next runnable task (PRD 12.D)."""
    state = _state()
    _require_init(state)
    task = state.next_runnable()
    if task is None:
        ui.info("No runnable task.")
        return
    ui.info(f"Next runnable task: {task.id} — {task.title} ({task.risk_level.value})")


@app.command()
def run(
    task_id: str = typer.Argument(..., help="Task id, e.g. T001"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Approve if gated"),
) -> None:
    """Run one task through executor (FR-07/08)."""
    from . import executor

    state = _state()
    _require_init(state)
    task = state.get_task(task_id)
    if task is None:
        ui.error(f"Unknown task '{task_id}'")
        raise typer.Exit(1)
    if task.status.value == "pending":
        state.advance(task_id, TaskEvent.activate)
    if not orchestrator.should_auto_run(task, state.config) and not yes:
        if not _prompt_approval(task):
            ui.warn("Not approved. Aborting.")
            raise typer.Exit(0)
    repo = scan_repo(state.root)
    handoff = executor.run_task(state, task, repo)
    hp = state.artifact_dir / "handoffs" / f"{task_id}.md"
    ui.ok(f"{task_id} -> {state.get_task(task_id).status.value}. Handoff: {hp}")
    ui.info(f"Tests: {handoff.test_result or 'n/a'}")


@app.command()
def review(requirement_id: str = typer.Argument(..., help="Requirement id, e.g. R001")) -> None:
    """Final review for a requirement (FR-11)."""
    state = _state()
    _require_init(state)
    repo = scan_repo(state.root)
    try:
        result = reviewer.review_requirement(state, requirement_id, repo)
    except KeyError as e:
        ui.error(str(e))
        raise typer.Exit(1)
    rp = state.artifact_dir / "reviews" / f"{result.id}.md"
    ui.ok(f"Review ({result.verdict}): {rp}")


@app.command()
def resume() -> None:
    """Report where the last session left off (FR-12)."""
    state = _state()
    _require_init(state)
    s = state.session
    ui.info(f"Requirement: {s.current_requirement_id or '-'} | Plan: {s.current_plan_id or '-'} | Last task: {s.last_task_id or '-'}")
    nxt = state.next_runnable()
    if nxt:
        ui.info(f"Next runnable: {nxt.id} — {nxt.title}")
    else:
        ui.info("No runnable task pending.")


def _prompt_approval(task) -> bool:
    return typer.confirm(f"Approve {task.id} ({task.risk_level.value}) '{task.title}'?", default=False)


@app.callback(invoke_without_command=True)
def _main(ctx: typer.Context) -> None:
    """Bare `plantod` opens the interactive session (PRD 11)."""
    from .config import load_dotenv

    load_dotenv(".")
    if ctx.invoked_subcommand is None:
        from .interactive import repl

        repl()


if __name__ == "__main__":
    app()
