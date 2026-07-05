"""PLANTOD command-line interface."""

from __future__ import annotations

from pathlib import Path

import typer

import shutil

from . import orchestrator, reviewer, ui
from .config import (
    config_path,
    global_config_path,
    load_global_config,
    update_role_backend,
    update_value,
)
from .repo import scan_repo
from .schemas import PROVIDERS, TaskEvent
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
    """Detect repo and scaffold .plantod/."""
    repo = scan_repo(".")
    if not repo.is_git:
        ui.warn("Current directory is not a git repo. Proceeding anyway.")
    state = StateManager(".")
    if state.is_initialized():
        ui.warn(f"Already initialized at {state.artifact_dir}")
        return
    state.initialize()
    ui.ok(f"Initialized {state.artifact_dir}")
    c = state.config
    ui.info(f"Mode: {c.mode} | Providers — planner: {c.planner.provider} | executor: {c.executor.provider} | reviewer: {c.reviewer.provider}")
    ui.info(f"Detected test command: {repo.test_command or 'none'}")
    _report_preflight(state)
    ui.info("Next: `plantod login` to set providers, then `plantod plan \"<request>\"`.")


def _report_preflight(state: StateManager) -> None:
    """Warn about any configured provider whose CLI isn't installed."""
    from . import preflight

    miss = preflight.missing(state.config)
    if not miss:
        ui.ok("All configured provider CLIs found.")
        return
    for m in miss:
        ui.warn(f"{m['role']} provider '{m['provider']}' needs the `{m['binary']}` CLI (not on PATH).")
    ui.info("Install the missing CLI(s), or pick another with `plantod login`.")


_ROLES = ("planner", "executor", "reviewer")

# fallback model shortcuts when a provider CLI can't be queried for a live list
_MODEL_PRESETS = {
    "claude-code": ["claude-opus-4-8", "claude-sonnet-5", "claude-haiku-4-5"],
    "codex": ["gpt-5-codex", "o4-mini"],
    "opencode": ["deepseek-v3", "deepseek-r1"],
}


def _pick_model(provider: str, current: str | None) -> str | None:
    from . import menu
    from .adapters.cliagent import list_models

    if provider == "mock":
        return None
    # try to fetch the real model list from the provider CLI; else use presets
    ui.info(f"  fetching models for {provider}…")
    fetched = list_models(provider)
    options = ["(default)"] + (fetched or _MODEL_PRESETS.get(provider, [])) + ["custom…"]
    # de-dup while preserving order, and surface the current value
    if current and current not in options:
        options.insert(1, current)
    seen, opts = set(), []
    for o in options:
        if o not in seen:
            seen.add(o)
            opts.append(o)
    default = current or "(default)"
    choice = menu.select(f"  model for {provider}" + (f" ({len(fetched)} available)" if fetched else ""), opts, default=default)
    if choice == "(default)":
        return None
    if choice == "custom…":
        val = typer.prompt("  model id").strip()
        return val or None
    return choice


def _verify_provider(provider: str) -> None:
    if provider == "mock":
        return
    from .adapters.cliagent import provider_binary

    binary = provider_binary(provider)
    if binary and shutil.which(binary) is None:
        ui.warn(f"'{binary}' CLI not found on PATH — install it before running {provider}.")
    else:
        ui.ok(f"{provider} ready ({binary or 'builtin'})")


@app.command()
def login(
    role: str = typer.Option(None, help=f"One of: {', '.join(_ROLES)}"),
    provider: str = typer.Option(None, help=f"One of: {', '.join(PROVIDERS)}"),
    model: str = typer.Option(None, help="Model id (optional; provider default if omitted)"),
    project: bool = typer.Option(False, "--project", help="Save to this repo instead of global"),
) -> None:
    """Configure provider + model per role (global by default, or --project)."""
    scope_path = config_path(StateManager(".").artifact_dir) if project else global_config_path()

    # non-interactive: set a single role
    if role or provider:
        if role not in _ROLES:
            ui.error(f"--role must be one of: {', '.join(_ROLES)}")
            raise typer.Exit(1)
        if provider not in PROVIDERS:
            ui.error(f"--provider must be one of: {', '.join(PROVIDERS)}")
            raise typer.Exit(1)
        update_role_backend(scope_path, role, provider, model)
        _verify_provider(provider)
        ui.ok(f"{role}: {provider}" + (f" ({model})" if model else "") + f" -> {scope_path}")
        return

    # interactive wizard — arrow-key selection
    from . import menu

    ui.info(f"Configuring providers ({'project' if project else 'global'}: {scope_path})")
    current = StateManager(".").config if project else load_global_config()
    for r in _ROLES:
        cur = getattr(current, r)
        ui.console.print(f"\n[bold]{r}[/bold] (current: {cur.provider}{f'/{cur.model}' if cur.model else ''})")
        try:
            chosen = menu.select(f"  provider for {r}", list(PROVIDERS), default=cur.provider)
            mdl = _pick_model(chosen, cur.model)
        except KeyboardInterrupt:
            ui.warn("Cancelled.")
            return
        update_role_backend(scope_path, r, chosen, mdl)
        _verify_provider(chosen)
    ui.ok(f"Saved provider config -> {scope_path}")


@app.command()
def mode(
    value: str = typer.Argument(None, help="auto | approval (omit to show current)"),
    project: bool = typer.Option(False, "--project", help="Save to this repo instead of global"),
) -> None:
    """Set run mode: `auto` (unattended) or `approval` (gate risky tasks)."""
    state = _state()
    if value is None:
        from . import menu

        ui.info(f"Current mode: {state.config.mode}")
        try:
            value = menu.select(
                "Run mode",
                [("approval — gate risky tasks", "approval"), ("auto — unattended to done", "auto")],
                default=state.config.mode,
            )
        except KeyboardInterrupt:
            ui.warn("Cancelled.")
            return
    if value not in ("auto", "approval"):
        ui.error("mode must be 'auto' or 'approval'")
        raise typer.Exit(1)
    scope = config_path(state.artifact_dir) if project else global_config_path()
    update_value(scope, "mode", value)
    ui.ok(f"mode: {value} -> {scope}")
    if value == "auto":
        ui.warn("Auto mode: tasks plan, execute, and review unattended — no approval prompts.")


@app.command()
def status() -> None:
    """Show board summary and current session."""
    state = _state()
    _require_init(state)
    counts: dict[str, int] = {}
    for t in state.board.tasks.values():
        counts[t.status.value] = counts.get(t.status.value, 0) + 1
    c = state.config
    ui.info(f"Mode: {c.mode} | Providers — planner: {c.planner.provider} | executor: {c.executor.provider} | reviewer: {c.reviewer.provider}")
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
    """Plan a request, break into tasks, and run the default flow."""
    state = _state()
    _require_init(state)
    approval = (lambda _t: True) if yes else _prompt_approval
    orchestrator.run_request(state, request, approval=approval, auto_review=review)


@app.command()
def tasks() -> None:
    """List tasks with status."""
    state = _state()
    _require_init(state)
    if not state.board.tasks:
        ui.info("No tasks yet. Run `plantod plan \"<request>\"`.")
        return
    ui.console.print(ui.tasks_table(list(state.board.tasks.values())))


@app.command()
def next() -> None:
    """Show the next runnable task."""
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
    """Run one task through executor."""
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
    """Final review for a requirement."""
    state = _state()
    _require_init(state)
    repo = scan_repo(state.root)
    try:
        result = reviewer.review_requirement(state, requirement_id, repo)
    except KeyError as e:
        ui.error(str(e))
        raise typer.Exit(1)
    except Exception as e:  # reviewer backend failed -> clean message
        ui.error(f"Review failed: {e}")
        raise typer.Exit(1)
    rp = state.artifact_dir / "reviews" / f"{result.id}.md"
    ui.ok(f"Review ({result.verdict}): {rp}")


@app.command()
def usage() -> None:
    """Estimated token usage (and cost, if prices configured) per provider."""
    from . import usage as usage_mod

    state = _state()
    _require_init(state)
    entries = state.board.usage
    if not entries:
        ui.info("No usage recorded yet.")
        return
    agg = usage_mod.summarize(entries)
    table = ui.Table(title="Estimated usage (heuristic)")
    table.add_column("Provider", style="bold")
    table.add_column("Calls", justify="right")
    table.add_column("Tokens in", justify="right")
    table.add_column("Tokens out", justify="right")
    for provider, a in sorted(agg.items()):
        table.add_row(provider, str(a["calls"]), f"{a['in']:,}", f"{a['out']:,}")
    ui.console.print(table)
    total = sum(e.tokens_in + e.tokens_out for e in entries)
    cost = usage_mod.estimate_cost(entries, state.config)
    ui.info(f"Total ~ {total:,} tokens" + (f" ~ ${cost}" if cost is not None else " (set `prices` in config for cost)"))


@app.command()
def resume() -> None:
    """Report where the last session left off."""
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
    """Bare `plantod` opens the interactive session."""
    from .config import load_dotenv

    load_dotenv(".")
    if ctx.invoked_subcommand is None:
        from .interactive import repl

        repl()


if __name__ == "__main__":
    app()
