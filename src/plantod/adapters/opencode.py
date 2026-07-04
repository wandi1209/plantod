"""OpenCode subprocess adapter for the executor role (PRD 14.1).

Drives a fast coding agent (e.g. DeepSeek via `opencode`) to perform one scoped
task. Captures changed files via git so we stay within `files_allowed`.
Robust to timeouts / nonzero exits (Technical Risk PRD 23).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from ..repo import RepoContext
from ..schemas import Handoff, Task
from .base import ExecResult, ModelAdapter, PlanResult, ReviewResult

_TIMEOUT_S = 900


class OpenCodeAdapter(ModelAdapter):
    name = "opencode"

    def __init__(self, model: str | None = None, binary: str = "opencode", timeout_s: int = _TIMEOUT_S):
        self.model = model
        self.binary = binary
        self.timeout_s = timeout_s

    def _git_dirty(self, root: Path) -> list[str]:
        try:
            out = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=root, capture_output=True, text=True, timeout=30,
            )
            return [line[3:] for line in out.stdout.splitlines() if line.strip()]
        except (subprocess.SubprocessError, OSError):
            return []

    def plan(self, request: str, repo: RepoContext) -> PlanResult:
        raise NotImplementedError("OpenCode adapter is executor-only; use the planner driver.")

    def execute(self, task: Task, repo: RepoContext) -> ExecResult:
        if shutil.which(self.binary) is None:
            return ExecResult(
                summary="",
                escalate=True,
                escalate_reason=f"'{self.binary}' CLI not found on PATH",
                raw="",
            )
        prompt = self._build_prompt(task)
        cmd = [self.binary, "run", prompt]
        if self.model:
            cmd[1:1] = ["--model", self.model]
        before = set(self._git_dirty(repo.root))
        try:
            proc = subprocess.run(
                cmd, cwd=repo.root, capture_output=True, text=True, timeout=self.timeout_s,
            )
        except subprocess.TimeoutExpired:
            return ExecResult(escalate=True, escalate_reason="executor timed out", raw="")
        except OSError as e:
            return ExecResult(escalate=True, escalate_reason=f"executor failed to launch: {e}", raw="")

        after = set(self._git_dirty(repo.root))
        changed = sorted(after - before) or sorted(after)
        if proc.returncode != 0:
            return ExecResult(
                files_changed=changed,
                summary=(proc.stdout or "")[-2000:],
                escalate=True,
                escalate_reason=f"executor exited {proc.returncode}: {(proc.stderr or '')[-300:]}",
                raw=proc.stdout,
            )
        return ExecResult(
            files_changed=changed,
            summary=(proc.stdout or "").strip()[-2000:],
            diff="",
            escalate=False,
            raw=proc.stdout,
        )

    def _build_prompt(self, task: Task) -> str:
        allowed = ", ".join(task.files_allowed) or "(unspecified — stay minimal)"
        forbidden = ", ".join(task.files_forbidden) or "(none)"
        crit = "\n".join(f"- {c}" for c in task.acceptance_criteria)
        guidance = f"Planner guidance: {task.planner_guidance}\n" if task.planner_guidance else ""
        return (
            f"Task {task.id}: {task.title}\n"
            f"Objective: {task.objective}\n"
            f"{guidance}"
            f"You MAY only edit these files: {allowed}\n"
            f"You MUST NOT edit: {forbidden}\n"
            f"Acceptance criteria:\n{crit}\n"
            f"Keep the change small and scoped. Do not refactor beyond the task.\n"
            f"If the task requires architecture decisions or cross-module changes, STOP "
            f"and say 'ESCALATE:' with the reason instead of editing."
        )

    def review(self, request: str, handoffs: list[Handoff], repo: RepoContext) -> ReviewResult:
        raise NotImplementedError("OpenCode adapter is executor-only; use the reviewer driver.")
