"""End-to-end orchestration: plan -> approval gate -> run -> escalate -> review.

PRD 11, 17.1, 17.2, 17.3.
"""

from __future__ import annotations

from collections.abc import Callable

from . import executor, planner, reviewer, ui
from .adapters import resolve
from .locking import LockBusy, project_lock
from .repo import RepoContext, scan_repo
from .schemas import RiskLevel, Role, Task, TaskEvent, TaskStatus
from .state import StateManager

# approval callback: (task) -> bool. Default denies high-risk automatically.
ApprovalFn = Callable[[Task], bool]

# risk considered "architecture / high impact" (PRD 17.2)
_HIGH = RiskLevel.high
_MAX_AUTORUN_FILES = 3


def should_auto_run(task: Task, config) -> bool:
    """Auto-run only low / controlled-medium risk with small clear scope (PRD 17.3)."""
    if config.mode == "auto":
        return True                            # unattended: run everything
    if not config.auto_run_small_tasks:
        return False
    if task.risk_level is _HIGH:
        return False
    if config.require_approval_for_architecture and task.risk_level is _HIGH:
        return False
    scope = [f for f in task.files_allowed if f != "*"]
    wide_scope = "*" in task.files_allowed or len(scope) > _MAX_AUTORUN_FILES
    if task.risk_level is RiskLevel.medium and wide_scope:
        return False
    if not task.test_command and config.test_before_done:
        return False
    return True


def _default_approval(_task: Task) -> bool:
    return False


def _try_replan(state: StateManager, task: Task, repo: RepoContext) -> bool:
    """Ask the planner to unblock an escalated task, then resolve it back to ready.

    Returns True if the task is retryable (PRD 12.F escalation -> planner loop).
    Capped by config.max_retries to avoid infinite loops (PRD 23).
    """
    if not state.config.auto_replan_on_escalation:
        return False
    if task.escalation_count > state.config.max_retries:
        state.log(f"{task.id} exceeded replan cap ({state.config.max_retries})")
        return False
    planner_adapter = resolve(Role.planner, state.config)
    reason = ""
    hp = state.artifact_dir / "handoffs" / f"{task.id}.md"
    if hp.exists():
        from .artifacts import read_doc

        fm, _ = read_doc(hp)
        reason = str(fm.get("risks_notes", ""))
    try:
        with ui.status(f"Re-planning {task.id} with {planner_adapter.label}…"):
            guidance = planner_adapter.advise(task, reason, repo)
    except Exception as exc:  # planner unavailable -> leave escalated
        state.log(f"{task.id} replan failed: {exc}")
        return False
    state.record_usage("planner", planner_adapter, task.requirement_id)
    task.planner_guidance = guidance
    state.advance(task.id, TaskEvent.resolve)   # needs_planner_review -> ready
    state.log(f"{task.id} replanned: {guidance[:200]}")
    state.save()
    return True


def run_request(
    state: StateManager,
    request: str,
    repo: RepoContext | None = None,
    approval: ApprovalFn | None = None,
    auto_review: bool = False,
    context: str = "",
) -> None:
    """Default flow for a natural-language request (PRD 17.1)."""
    try:
        with project_lock(state.artifact_dir):
            _run_request_locked(state, request, repo, approval, auto_review, context)
    except LockBusy as e:
        ui.error(str(e))


def _run_request_locked(state, request, repo, approval, auto_review, context="") -> None:
    approval = approval or _default_approval
    if state.config.mode == "auto":
        auto_review = True                     # run through review to done, unattended
    repo = repo or scan_repo(state.root)

    ui.info(f"Reading request: {request}")
    ui.info("Scanning repository...")

    try:
        plan, tasks = planner.make_plan(state, request, repo, context=context)
    except Exception as exc:  # planner backend failed -> clean message, no traceback
        ui.error(f"Planning failed: {exc}")
        return
    plan_path = state.artifact_dir / "plans" / f"{plan.id}.md"
    ui.ok(f"Plan created: {plan_path}")
    ui.ok(f"{len(tasks)} tasks generated")

    # activate all pending tasks whose deps are (initially) empty -> ready
    for task in tasks:
        state.advance(task.id, TaskEvent.activate)   # pending -> ready
    state.save()

    while (task := state.next_runnable()) is not None:
        gated = should_auto_run(task, state.config)
        if gated:
            ui.info(f"Auto-running {task.id} ({task.risk_level.value}): {task.title}")
        else:
            ui.warn(f"Approval needed for {task.id} ({task.risk_level.value}): {task.title}")
            if not approval(task):
                ui.warn(f"{task.id} skipped (not approved). Stopping run.")
                break

        handoff = executor.run_task(state, task, repo)
        hp = state.artifact_dir / "handoffs" / f"{task.id}.md"
        current = state.get_task(task.id)
        if current.status is TaskStatus.needs_planner_review:
            ui.error(f"{task.id} escalated: {handoff.risks_notes.replace('ESCALATED: ', '')}")
            if _try_replan(state, current, repo):
                ui.info(f"Planner advised {task.id}; retrying (attempt {current.escalation_count}).")
                continue
            ui.warn("Escalation unresolved. Fix and run `plantod resume`.")
            break
        ui.ok(f"{task.id} -> {current.status.value}. Handoff: {hp}")

    if auto_review and plan.requirement_id:
        review = reviewer.review_requirement(state, plan.requirement_id, repo)
        rp = state.artifact_dir / "reviews" / f"{review.id}.md"
        ui.ok(f"Review ({review.verdict}): {rp}")

    nxt = state.next_runnable()
    if nxt:
        ui.info(f"Next runnable task: {nxt.id}")

    _print_usage(state, plan.requirement_id)


def _print_usage(state: StateManager, requirement_id: str | None) -> None:
    from . import usage

    entries = [e for e in state.board.usage if e.requirement_id == requirement_id]
    if not entries:
        return
    total_in = sum(e.tokens_in for e in entries)
    total_out = sum(e.tokens_out for e in entries)
    cost = usage.estimate_cost(entries, state.config)
    line = f"Est. tokens ~ {total_in + total_out:,} (in {total_in:,} / out {total_out:,})"
    if cost is not None:
        line += f" ~ ${cost}"
    ui.info(line + "  [estimated]")
