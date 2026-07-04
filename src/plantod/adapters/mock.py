"""Deterministic mock adapter — runs the full flow offline, no API keys (PRD 24 mitigation)."""

from __future__ import annotations

from ..repo import RepoContext
from ..schemas import Handoff, Task
from .base import ExecResult, ModelAdapter, PlanResult, ReviewResult


class MockAdapter(ModelAdapter):
    name = "mock"

    def plan(self, request: str, repo: RepoContext) -> PlanResult:
        slug = "-".join(request.lower().split()[:3]) or "task"
        tasks = [
            {
                "id": "T001",
                "title": f"Scaffold for: {request}",
                "objective": f"Set up minimal structure for '{request}'.",
                "files_allowed": ["*"],
                "acceptance_criteria": ["structure exists"],
                "test_command": repo.test_command,
                "risk_level": "low",
                "depends_on": [],
            },
            {
                "id": "T002",
                "title": f"Implement: {request}",
                "objective": f"Implement core behavior for '{request}'.",
                "files_allowed": ["*"],
                "acceptance_criteria": ["behavior works", "tests pass"],
                "test_command": repo.test_command,
                "risk_level": "medium",
                "depends_on": ["T001"],
            },
        ]
        return PlanResult(
            title=f"Plan for {slug}",
            summary=f"Mock plan for request '{request}'. Two tasks.",
            risk_level="medium",
            tasks=tasks,
            raw="mock",
        )

    def execute(self, task: Task, repo: RepoContext) -> ExecResult:
        return ExecResult(
            files_changed=[f for f in task.files_allowed if f != "*"] or ["(mock) no files"],
            summary=f"Mock executed {task.id}: {task.objective}",
            diff="",
            escalate=task.risk_level.value == "high",
            escalate_reason="high risk (mock)" if task.risk_level.value == "high" else "",
            raw="mock",
        )

    def review(self, request: str, handoffs: list[Handoff], repo: RepoContext) -> ReviewResult:
        return ReviewResult(
            verdict="approve",
            summary=f"Mock review of '{request}': {len(handoffs)} handoff(s) look consistent.",
            findings=[],
            raw="mock",
        )
