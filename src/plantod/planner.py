"""Planner layer: turn a request into a Plan + Tasks and persist them (PRD 12.C, FR-04/05)."""

from __future__ import annotations

from datetime import date

from .adapters import resolve
from .repo import RepoContext
from .schemas import Plan, Requirement, Role, Task
from .state import StateManager


def _slug(text: str) -> str:
    return "-".join("".join(c if c.isalnum() or c == " " else " " for c in text).split()[:4]).lower()


def make_plan(state: StateManager, request: str, repo: RepoContext) -> tuple[Plan, list[Task]]:
    """Run the planner adapter and persist requirement, plan, and tasks."""
    adapter = resolve(Role.planner, state.config)

    req_id = f"R{len(state.board.requirements) + 1:03d}"
    requirement = state.add_requirement(Requirement(id=req_id, request=request))

    result = adapter.plan(request, repo)

    plan_id = f"{date.today().isoformat()}-{_slug(request) or 'plan'}"
    tasks: list[Task] = []
    for raw in result.tasks:
        raw.setdefault("assignee_role", Role.executor.value)
        raw["requirement_id"] = req_id
        task = Task(**raw)
        tasks.append(state.add_task(task))

    plan = Plan(
        id=plan_id,
        requirement_id=req_id,
        title=result.title,
        summary=result.summary,
        risk_level=result.risk_level,
        task_ids=[t.id for t in tasks],
    )
    state.add_plan(plan, _plan_body(plan, result.summary, tasks))
    state.save()
    return plan, tasks


def _plan_body(plan: Plan, summary: str, tasks: list[Task]) -> str:
    lines = [f"# {plan.title}", "", summary, "", "## Tasks", ""]
    for t in tasks:
        lines.append(f"- **{t.id}** ({t.risk_level.value}) {t.title}")
    return "\n".join(lines)
