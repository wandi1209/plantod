"""Reviewer layer: final review over a requirement's handoffs (PRD 12.G, FR-11)."""

from __future__ import annotations

from .adapters import resolve
from .artifacts import read_doc
from .repo import RepoContext
from .schemas import Handoff, Review, Role
from .state import StateManager


def _load_handoffs(state: StateManager, task_ids: list[str]) -> list[Handoff]:
    handoffs: list[Handoff] = []
    for tid in task_ids:
        path = state.artifact_dir / "handoffs" / f"{tid}.md"
        if path.exists():
            fm, _ = read_doc(path)
            try:
                handoffs.append(Handoff(**fm))
            except Exception:  # tolerate partial handoffs
                continue
    return handoffs


def review_requirement(state: StateManager, requirement_id: str, repo: RepoContext) -> Review:
    req = state.board.requirements.get(requirement_id)
    if req is None:
        raise KeyError(f"unknown requirement '{requirement_id}'")

    task_ids = [t.id for t in state.board.tasks.values() if t.requirement_id == requirement_id]
    handoffs = _load_handoffs(state, task_ids)

    adapter = resolve(Role.reviewer, state.config)
    from .retry import with_retries

    from . import ui

    with ui.status(f"Reviewing with {adapter.label}…"):
        result = with_retries(
            lambda: adapter.review(req.request, handoffs, repo),
            attempts=state.config.max_retries,
        )
    state.record_usage("reviewer", adapter, requirement_id)

    review = Review(
        id=f"{requirement_id}-review",
        requirement_id=requirement_id,
        verdict=result.verdict,
        summary=result.summary,
        findings=result.findings,
    )
    body = _review_body(review)
    state.write_review(review, body)

    # advance done tasks to reviewed
    from .schemas import TaskEvent, TaskStatus

    for tid in task_ids:
        task = state.board.tasks.get(tid)
        if task and task.status is TaskStatus.done:
            state.advance(tid, TaskEvent.review)
    state.save()
    return review


def _review_body(review: Review) -> str:
    findings = "\n".join(f"- {f}" for f in review.findings) or "- (none)"
    return (
        f"# Review {review.id}\n\n"
        f"**Verdict:** {review.verdict}\n\n"
        f"{review.summary}\n\n"
        f"## Findings\n{findings}\n"
    )
