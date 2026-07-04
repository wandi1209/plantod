"""Anthropic Claude adapter for planner + reviewer roles (PRD 14.1).

Planner/reviewer default to a strong model (Claude Opus). Requires ANTHROPIC_API_KEY.
"""

from __future__ import annotations

import os

from ..parsing import extract_json
from ..repo import RepoContext
from ..schemas import Handoff, Task
from .base import ExecResult, ModelAdapter, PlanResult, ReviewResult

_PLAN_SYS = """You are PLANTOD's PLANNER. Read the request and repo context, then produce a
small, scoped, testable plan. Break work into the fewest tasks that each touch a
narrow file scope. Respond with a short markdown summary followed by ONE fenced
```json block matching exactly:
{"title": str, "summary": str, "risk_level": "low|medium|high",
 "tasks": [{"id": "T001", "title": str, "objective": str,
            "files_allowed": [str], "acceptance_criteria": [str],
            "test_command": str|null, "risk_level": "low|medium|high",
            "depends_on": [str]}]}"""

_REVIEW_SYS = """You are PLANTOD's REVIEWER. Given the original request and task handoffs,
judge alignment and quality. Respond with markdown then ONE fenced ```json block:
{"verdict": "approve|revise", "summary": str, "findings": [str]}"""


class ClaudeAdapter(ModelAdapter):
    name = "claude"

    def __init__(self, model: str = "claude-opus-4-8"):
        self.model = model
        self._client = None

    def _client_lazy(self):
        if self._client is None:
            if not os.environ.get("ANTHROPIC_API_KEY"):
                raise RuntimeError(
                    "ANTHROPIC_API_KEY not set — required for the Claude adapter. "
                    "Use executor_driver/planner_driver 'mock' to run offline."
                )
            import anthropic

            self._client = anthropic.Anthropic()
        return self._client

    def _complete(self, system: str, user: str, max_tokens: int = 4096) -> str:
        resp = self._client_lazy().messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(block.text for block in resp.content if block.type == "text")

    def plan(self, request: str, repo: RepoContext) -> PlanResult:
        user = f"REQUEST:\n{request}\n\nREPO CONTEXT:\n{repo.summary()}"
        raw = self._complete(_PLAN_SYS, user)
        data = extract_json(raw)
        return PlanResult(
            title=data.get("title", request),
            summary=data.get("summary", ""),
            risk_level=data.get("risk_level", "medium"),
            tasks=data.get("tasks", []),
            raw=raw,
        )

    def execute(self, task: Task, repo: RepoContext) -> ExecResult:
        raise NotImplementedError("Claude adapter does not execute tasks; use the executor driver.")

    def advise(self, task: Task, reason: str, repo: RepoContext) -> str:
        sys = (
            "You are PLANTOD's PLANNER unblocking an escalated task. Give concise, "
            "concrete guidance (2-5 sentences) so a fast executor can retry within a "
            "narrow scope. Do not write code."
        )
        user = (
            f"TASK {task.id}: {task.title}\nOBJECTIVE: {task.objective}\n"
            f"ALLOWED FILES: {task.files_allowed}\nBLOCK REASON: {reason}\n"
            f"REPO:\n{repo.summary(30)}"
        )
        return self._complete(sys, user, max_tokens=1024).strip()

    def review(self, request: str, handoffs: list[Handoff], repo: RepoContext) -> ReviewResult:
        hs = "\n\n".join(
            f"[{h.task_id}] {h.summary_of_changes}\n"
            f"tests: {h.test_result}\nrisks: {h.risks_notes}"
            for h in handoffs
        )
        user = f"REQUEST:\n{request}\n\nHANDOFFS:\n{hs}\n\nREPO:\n{repo.summary(30)}"
        raw = self._complete(_REVIEW_SYS, user)
        data = extract_json(raw)
        return ReviewResult(
            verdict=data.get("verdict", "approve"),
            summary=data.get("summary", ""),
            findings=data.get("findings", []),
            raw=raw,
        )
