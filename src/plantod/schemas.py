"""Pydantic schemas for PLANTOD artifacts, config, and the task state machine.

Covers PRD sections 18 (state machine) and 19 (data formats).
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #
class RiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class Role(str, Enum):
    planner = "planner"
    executor = "executor"
    reviewer = "reviewer"


class TaskStatus(str, Enum):
    pending = "pending"
    ready = "ready"
    in_progress = "in_progress"
    blocked = "blocked"
    needs_planner_review = "needs_planner_review"
    testing = "testing"
    done = "done"
    reviewed = "reviewed"
    cancelled = "cancelled"


class TaskEvent(str, Enum):
    """Events that drive task state transitions (PRD 18)."""

    activate = "activate"          # pending -> ready
    start = "start"               # ready -> in_progress
    submit_test = "submit_test"    # in_progress -> testing
    pass_test = "pass_test"        # testing -> done
    fail_test = "fail_test"        # testing -> in_progress
    block = "block"               # in_progress -> blocked
    escalate = "escalate"          # blocked -> needs_planner_review
    resolve = "resolve"           # needs_planner_review -> ready
    review = "review"             # done -> reviewed
    cancel = "cancel"             # any -> cancelled


# Allowed transitions: (status, event) -> next status  (PRD 18)
TRANSITIONS: dict[tuple[TaskStatus, TaskEvent], TaskStatus] = {
    (TaskStatus.pending, TaskEvent.activate): TaskStatus.ready,
    (TaskStatus.ready, TaskEvent.start): TaskStatus.in_progress,
    (TaskStatus.in_progress, TaskEvent.submit_test): TaskStatus.testing,
    (TaskStatus.testing, TaskEvent.pass_test): TaskStatus.done,
    (TaskStatus.testing, TaskEvent.fail_test): TaskStatus.in_progress,
    (TaskStatus.in_progress, TaskEvent.block): TaskStatus.blocked,
    (TaskStatus.blocked, TaskEvent.escalate): TaskStatus.needs_planner_review,
    (TaskStatus.needs_planner_review, TaskEvent.resolve): TaskStatus.ready,
    (TaskStatus.done, TaskEvent.review): TaskStatus.reviewed,
}

# cancel is legal from any non-terminal state
_CANCELLABLE = {
    TaskStatus.pending,
    TaskStatus.ready,
    TaskStatus.in_progress,
    TaskStatus.blocked,
    TaskStatus.needs_planner_review,
    TaskStatus.testing,
}


class IllegalTransition(Exception):
    """Raised when an event is not allowed from the current status."""


def next_status(current: TaskStatus, event: TaskEvent) -> TaskStatus:
    """Return the resulting status for (current, event) or raise IllegalTransition."""
    if event is TaskEvent.cancel:
        if current in _CANCELLABLE:
            return TaskStatus.cancelled
        raise IllegalTransition(f"cannot cancel from {current.value}")
    try:
        return TRANSITIONS[(current, event)]
    except KeyError:
        raise IllegalTransition(
            f"event {event.value} not allowed from {current.value}"
        ) from None


# --------------------------------------------------------------------------- #
# Config (PRD 19.1)
# --------------------------------------------------------------------------- #
class Config(BaseModel):
    planner: str = "claude-opus"
    executor: str = "deepseek-v4-flash"
    reviewer: str = "claude-opus"
    executor_driver: str = "opencode"          # opencode | mock
    planner_driver: str = "claude"             # claude | mock
    reviewer_driver: str = "claude"            # claude | mock
    auto_run_small_tasks: bool = True
    require_approval_for_architecture: bool = True
    test_before_done: bool = True
    artifact_path: str = ".plantod"
    # model ids resolved by adapters
    claude_model: str = "claude-opus-4-8"


# --------------------------------------------------------------------------- #
# Artifacts (PRD 19.2 / 19.3 + requirement/plan/review/board/session)
# --------------------------------------------------------------------------- #
class Task(BaseModel):
    id: str
    title: str
    objective: str
    files_allowed: list[str] = Field(default_factory=list)
    files_forbidden: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    test_command: str | None = None
    risk_level: RiskLevel = RiskLevel.low
    status: TaskStatus = TaskStatus.pending
    depends_on: list[str] = Field(default_factory=list)
    escalation_rules: list[str] = Field(default_factory=list)
    assignee_role: Role = Role.executor
    requirement_id: str | None = None
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


class Handoff(BaseModel):
    task_id: str
    status: str
    model_used: str
    files_changed: list[str] = Field(default_factory=list)
    summary_of_changes: str = ""
    tests_run: str | None = None
    test_result: str | None = None
    risks_notes: str = ""
    next_recommendation: str = ""
    created_at: str = Field(default_factory=_now)


class Requirement(BaseModel):
    id: str
    request: str
    notes: str = ""
    created_at: str = Field(default_factory=_now)


class Plan(BaseModel):
    id: str
    requirement_id: str
    title: str
    summary: str
    risk_level: RiskLevel = RiskLevel.medium
    task_ids: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=_now)


class Review(BaseModel):
    id: str
    requirement_id: str
    verdict: str = "approve"          # approve | revise
    summary: str = ""
    findings: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=_now)


class Board(BaseModel):
    """Aggregate task board persisted as board.json (PRD 12.2)."""

    tasks: dict[str, Task] = Field(default_factory=dict)
    requirements: dict[str, Requirement] = Field(default_factory=dict)
    plans: dict[str, Plan] = Field(default_factory=dict)
    updated_at: str = Field(default_factory=_now)


class Session(BaseModel):
    """Lightweight session state persisted as session.json (PRD 12.2)."""

    current_requirement_id: str | None = None
    current_plan_id: str | None = None
    last_task_id: str | None = None
    history: list[str] = Field(default_factory=list)   # summary + last-N turns
    updated_at: str = Field(default_factory=_now)
