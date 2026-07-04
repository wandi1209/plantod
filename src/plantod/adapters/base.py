"""ModelAdapter interface + result types (PRD 14.1, NFR-03)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from ..repo import RepoContext
from ..schemas import Handoff, Task


@dataclass
class PlanResult:
    title: str
    summary: str
    risk_level: str
    # each task dict is validated into a Task by the planner layer
    tasks: list[dict] = field(default_factory=list)
    raw: str = ""


@dataclass
class ExecResult:
    files_changed: list[str] = field(default_factory=list)
    summary: str = ""
    diff: str = ""
    escalate: bool = False
    escalate_reason: str = ""
    raw: str = ""


@dataclass
class ReviewResult:
    verdict: str = "approve"          # approve | revise
    summary: str = ""
    findings: list[str] = field(default_factory=list)
    raw: str = ""


class ModelAdapter(ABC):
    """Backend-agnostic model interface. Concrete adapters wrap a provider."""

    name: str = "adapter"

    @abstractmethod
    def plan(self, request: str, repo: RepoContext) -> PlanResult: ...

    @abstractmethod
    def execute(self, task: Task, repo: RepoContext) -> ExecResult: ...

    @abstractmethod
    def review(self, request: str, handoffs: list[Handoff], repo: RepoContext) -> ReviewResult: ...
