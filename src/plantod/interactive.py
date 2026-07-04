"""Interactive chat session — bare `plantod` (PRD 11, 12.B, FR-03).

Inline REPL (Claude-Code style): scrollback in the terminal, arrow-key history,
ctrl-r search, slash-command autocomplete, and multi-turn conversation memory.
Falls back to a plain input() loop if prompt_toolkit is unavailable.
"""

from __future__ import annotations

from . import conversation, orchestrator, reviewer, ui
from .repo import scan_repo
from .state import StateManager

_SLASH = {
    "/help": "show this help",
    "/status": "board summary",
    "/tasks": "list tasks",
    "/usage": "estimated token usage",
    "/review": "/review <RID> — final review a requirement",
    "/clear": "clear conversation memory",
    "/resume": "where the last session left off",
    "/quit": "exit",
}

_BANNER = "PLANTOD — Plan, Task, Orchestrate, Deliver.  Type a request, or /help."


def repl() -> None:
    state = StateManager(".")
    if not state.is_initialized():
        ui.warn("Not initialized. Run `plantod init` first.")
        return

    ui.console.print(f"[bold cyan]{_BANNER}[/bold cyan]")
    if state.session.turns:
        ui.info(f"Resumed session — {len(state.session.turns)} prior turn(s). /clear to reset.")
    repo = scan_repo(state.root)
    ask = _make_prompt(state)

    while True:
        try:
            line = ask()
        except (EOFError, KeyboardInterrupt):
            ui.console.print()
            break
        line = line.strip()
        if not line:
            continue
        if line in ("/quit", "/exit"):
            break
        if _handle_slash(state, repo, line):
            continue
        _handle_request(state, repo, line)


# --------------------------------------------------------------------------- #
# Input backend
# --------------------------------------------------------------------------- #
def _make_prompt(state: StateManager):
    """Return a callable that reads one line, using prompt_toolkit if available."""
    import sys

    if not sys.stdin.isatty():
        return lambda: input("plantod> ")
    try:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
        from prompt_toolkit.completion import WordCompleter
        from prompt_toolkit.history import FileHistory
    except ImportError:
        return lambda: input("plantod> ")

    history_path = state.artifact_dir / "logs" / "repl_history"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    session = PromptSession(
        history=FileHistory(str(history_path)),
        auto_suggest=AutoSuggestFromHistory(),
        completer=WordCompleter(list(_SLASH), sentence=True),
    )
    return lambda: session.prompt("plantod › ")


# --------------------------------------------------------------------------- #
# Handlers
# --------------------------------------------------------------------------- #
def _handle_slash(state: StateManager, repo, line: str) -> bool:
    """Return True if the line was a slash command (handled)."""
    if not line.startswith("/"):
        return False
    cmd, _, arg = line.partition(" ")
    arg = arg.strip()

    if cmd == "/help":
        for name, desc in _SLASH.items():
            ui.console.print(f"  [bold]{name}[/bold]  {desc}")
    elif cmd == "/status":
        _status(state)
    elif cmd == "/tasks":
        if state.board.tasks:
            ui.console.print(ui.tasks_table(list(state.board.tasks.values())))
        else:
            ui.info("No tasks yet.")
    elif cmd == "/usage":
        _usage(state)
    elif cmd == "/clear":
        state.session.turns.clear()
        state.save()
        ui.ok("Conversation memory cleared.")
    elif cmd == "/resume":
        s = state.session
        ui.info(f"Requirement: {s.current_requirement_id or '-'} | Last task: {s.last_task_id or '-'}")
        nxt = state.next_runnable()
        if nxt:
            ui.info(f"Next runnable: {nxt.id} — {nxt.title}")
    elif cmd == "/review":
        if not arg:
            ui.error("Usage: /review <requirement-id>")
        else:
            try:
                r = reviewer.review_requirement(state, arg, repo)
                ui.ok(f"Review ({r.verdict}) written.")
            except KeyError as e:
                ui.error(str(e))
    else:
        ui.error(f"Unknown command {cmd}. /help for list.")
    return True


def _handle_request(state: StateManager, repo, line: str) -> None:
    context = conversation.build_context(state)   # prior turns only
    conversation.record(state, "user", line)
    orchestrator.run_request(state, line, repo=repo, approval=_confirm, context=context)
    # summarize outcome as the plantod turn
    plan_id = state.session.current_plan_id
    plan = state.board.plans.get(plan_id) if plan_id else None
    summary = plan.summary if plan else "handled request"
    conversation.record(state, "plantod", summary)
    state.save()


def _confirm(task) -> bool:
    ans = input(f"Approve {task.id} ({task.risk_level.value}) '{task.title}'? [y/N] ").strip().lower()
    return ans in ("y", "yes")


def _status(state: StateManager) -> None:
    counts: dict[str, int] = {}
    for t in state.board.tasks.values():
        counts[t.status.value] = counts.get(t.status.value, 0) + 1
    c = state.config
    ui.info(f"Providers — planner: {c.planner.provider} | executor: {c.executor.provider} | reviewer: {c.reviewer.provider}")
    ui.info(
        f"Requirements: {len(state.board.requirements)} | Tasks: {len(state.board.tasks)} | "
        + ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
    )


def _usage(state: StateManager) -> None:
    from . import usage as usage_mod

    if not state.board.usage:
        ui.info("No usage recorded yet.")
        return
    total = sum(e.tokens_in + e.tokens_out for e in state.board.usage)
    cost = usage_mod.estimate_cost(state.board.usage, state.config)
    ui.info(f"Est. usage ~ {total:,} tokens" + (f" ~ ${cost}" if cost is not None else "") + "  [estimated]")
