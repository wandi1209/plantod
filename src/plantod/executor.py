"""Executor layer: run one scoped task, enforce scope, test, handoff, escalate.

PRD 12.E / 12.F, FR-07/08/09. Scope is enforced by reverting out-of-scope edits,
not merely by prompting (production guardrail).
"""

from __future__ import annotations

from . import gitutil, scope
from .adapters import resolve
from .repo import RepoContext
from .retry import with_retries
from .schemas import Handoff, Role, Task, TaskEvent
from .testrunner import run_tests


def _escalate(state, task: Task, adapter_name: str, files, summary: str, reason: str) -> Handoff:
    task.escalation_count += 1
    state.advance(task.id, TaskEvent.block)
    state.advance(task.id, TaskEvent.escalate)
    handoff = Handoff(
        task_id=task.id,
        status=task.status.value,
        model_used=adapter_name,
        files_changed=list(files),
        summary_of_changes=summary,
        risks_notes=f"ESCALATED: {reason}",
        next_recommendation="Route to planner for guidance, then retry with narrower scope.",
    )
    state.write_handoff(handoff)
    state.log(f"{task.id} escalated (#{task.escalation_count}): {reason}")
    state.save()
    return handoff


def run_task(state, task: Task, repo: RepoContext) -> Handoff:
    """Execute a single task through its state-machine lifecycle."""
    adapter = resolve(Role.executor, state.config)
    state.advance(task.id, TaskEvent.start)          # ready -> in_progress
    state.log(f"{task.id} start ({adapter.name})")

    before = gitutil.changed_files(repo.root) if gitutil.is_git_repo(repo.root) else set()

    from . import ui

    try:
        with ui.status(f"{task.id}: executing with {adapter.label}…"):
            result = with_retries(
                lambda: adapter.execute(task, repo),
                attempts=state.config.max_retries,
                on_retry=lambda n, e: state.log(f"{task.id} execute retry {n}: {e}"),
            )
    except Exception as exc:  # backend failed hard after retries
        return _escalate(state, task, adapter.label, [], "", f"executor error: {exc}")

    state.record_usage("executor", adapter, task.requirement_id)

    if result.escalate:
        return _escalate(state, task, adapter.label, result.files_changed, result.summary, result.escalate_reason)

    # --- hard scope enforcement (PRD 12.E) -------------------------------- #
    files_changed = result.files_changed
    if state.config.enforce_scope and gitutil.is_git_repo(repo.root):
        after = gitutil.changed_files(repo.root)
        report = scope.enforce(
            repo.root, after - before, task.files_allowed, task.files_forbidden
        )
        files_changed = report.in_scope
        if not report.clean:
            reason = f"out-of-scope edits reverted: {report.reverted or report.violations}"
            return _escalate(state, task, adapter.label, report.in_scope, result.summary, reason)

    # --- testing phase ---------------------------------------------------- #
    state.advance(task.id, TaskEvent.submit_test)     # -> testing
    test_cmd = task.test_command if state.config.test_before_done else None
    test = run_tests(test_cmd, repo.root, timeout=state.config.test_timeout_s)

    if test.ran and not test.passed:
        state.advance(task.id, TaskEvent.fail_test)   # -> in_progress
        next_rec = "Tests failed; fix or escalate."
    else:
        state.advance(task.id, TaskEvent.pass_test)   # -> done
        next_rec = "Task done; ready for review."

    handoff = Handoff(
        task_id=task.id,
        status=task.status.value,
        model_used=adapter.label,
        files_changed=files_changed,
        summary_of_changes=result.summary,
        tests_run=test.command,
        test_result=test.summary + (f"\n{test.output}" if test.output else ""),
        risks_notes="",
        next_recommendation=next_rec,
    )
    state.write_handoff(handoff)
    state.log(f"{task.id} -> {task.status.value} (tests: {test.summary})")
    state.save()
    return handoff
