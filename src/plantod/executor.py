"""Executor layer: run one scoped task, test, write handoff, detect escalation.

PRD 12.E / 12.F, FR-07/08/09.
"""

from __future__ import annotations

from .adapters import resolve
from .repo import RepoContext
from .schemas import Handoff, Role, Task, TaskEvent
from .state import StateManager
from .testrunner import run_tests


def run_task(state: StateManager, task: Task, repo: RepoContext) -> Handoff:
    """Execute a single task through its state-machine lifecycle."""
    adapter = resolve(Role.executor, state.config)
    state.advance(task.id, TaskEvent.start)          # ready -> in_progress
    state.log(f"{task.id} start ({adapter.name})")

    result = adapter.execute(task, repo)

    if result.escalate:
        state.advance(task.id, TaskEvent.block)       # -> blocked
        state.advance(task.id, TaskEvent.escalate)    # -> needs_planner_review
        handoff = Handoff(
            task_id=task.id,
            status=task.status.value,
            model_used=adapter.name,
            files_changed=result.files_changed,
            summary_of_changes=result.summary,
            risks_notes=f"ESCALATED: {result.escalate_reason}",
            next_recommendation="Route to planner/reviewer for guidance.",
        )
        state.write_handoff(handoff)
        state.log(f"{task.id} escalated: {result.escalate_reason}")
        state.save()
        return handoff

    # testing phase
    state.advance(task.id, TaskEvent.submit_test)     # -> testing
    test_cmd = task.test_command if state.config.test_before_done else None
    test = run_tests(test_cmd, repo.root)

    if test.ran and not test.passed:
        state.advance(task.id, TaskEvent.fail_test)   # -> in_progress
        next_rec = "Tests failed; fix or escalate."
    else:
        state.advance(task.id, TaskEvent.pass_test)   # -> done
        next_rec = "Task done; ready for review."

    handoff = Handoff(
        task_id=task.id,
        status=task.status.value,
        model_used=adapter.name,
        files_changed=result.files_changed,
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
