"""StateManager: owns .plantod/ paths, board.json, session.json, and the task state machine.

Central persistence hub for artifacts (PRD 12.D, 12.2, FR-02, FR-12).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from . import artifacts
from .config import load_config, save_config
from .schemas import (
    Board,
    Config,
    Handoff,
    Plan,
    Requirement,
    Review,
    Session,
    Task,
    TaskEvent,
    TaskStatus,
    next_status,
)

BOARD_FILE = "board.json"
SESSION_FILE = "session.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class StateManager:
    """Loads and persists all project state under an artifact directory."""

    def __init__(self, root: Path | str = "."):
        self.root = Path(root).resolve()
        self.config: Config = load_config(self._artifact_dir_guess())
        self.artifact_dir = self.root / self.config.artifact_path
        self.board: Board = self._load_board()
        self.session: Session = self._load_session()

    # -- paths ------------------------------------------------------------- #
    def _artifact_dir_guess(self) -> Path:
        # config may customize artifact_path; default .plantod resolves fine
        return self.root / ".plantod"

    @property
    def board_path(self) -> Path:
        return self.artifact_dir / BOARD_FILE

    @property
    def session_path(self) -> Path:
        return self.artifact_dir / SESSION_FILE

    def is_initialized(self) -> bool:
        return self.artifact_dir.exists() and (self.artifact_dir / "config.yaml").exists()

    # -- init -------------------------------------------------------------- #
    def initialize(self) -> None:
        artifacts.scaffold(self.artifact_dir)
        save_config(self.config, self.artifact_dir)
        self.save()

    # -- load/save --------------------------------------------------------- #
    def _load_board(self) -> Board:
        data = artifacts.read_json(self.board_path)
        return Board(**data) if data else Board()

    def _load_session(self) -> Session:
        data = artifacts.read_json(self.session_path)
        return Session(**data) if data else Session()

    def save(self) -> None:
        self.board.updated_at = _now()
        self.session.updated_at = _now()
        artifacts.write_json(self.board_path, self.board.model_dump(mode="json"))
        artifacts.write_json(self.session_path, self.session.model_dump(mode="json"))

    # -- requirements / plans --------------------------------------------- #
    def add_requirement(self, req: Requirement) -> Requirement:
        self.board.requirements[req.id] = req
        self.session.current_requirement_id = req.id
        artifacts.write_doc(
            self.artifact_dir / "requirements" / f"{req.id}.md",
            {"id": req.id, "created_at": req.created_at},
            f"# Requirement {req.id}\n\n{req.request}\n\n{req.notes}",
        )
        return req

    def add_plan(self, plan: Plan, body: str) -> Plan:
        self.board.plans[plan.id] = plan
        self.session.current_plan_id = plan.id
        artifacts.write_doc(
            self.artifact_dir / "plans" / f"{plan.id}.md",
            plan.model_dump(mode="json"),
            body,
        )
        return plan

    # -- tasks ------------------------------------------------------------- #
    def add_task(self, task: Task) -> Task:
        self.board.tasks[task.id] = task
        self._write_task_doc(task)
        return task

    def get_task(self, task_id: str) -> Task | None:
        return self.board.tasks.get(task_id)

    def _write_task_doc(self, task: Task) -> None:
        body = (
            f"# {task.id} — {task.title}\n\n"
            f"## Objective\n{task.objective}\n\n"
            f"## Acceptance Criteria\n"
            + "\n".join(f"- {c}" for c in task.acceptance_criteria)
            + "\n"
        )
        artifacts.write_doc(
            self.artifact_dir / "tasks" / f"{task.id}.md",
            task.model_dump(mode="json"),
            body,
        )

    def advance(self, task_id: str, event: TaskEvent) -> Task:
        """Apply a state-machine transition and persist. Raises IllegalTransition."""
        task = self.board.tasks[task_id]
        task.status = next_status(task.status, event)
        task.updated_at = _now()
        self._write_task_doc(task)
        self.session.last_task_id = task_id
        return task

    def next_runnable(self) -> Task | None:
        """First `ready` task whose dependencies are all `done`/`reviewed` (PRD 12.D)."""
        terminal = {TaskStatus.done, TaskStatus.reviewed}
        for task in self.board.tasks.values():
            if task.status is not TaskStatus.ready:
                continue
            if all(
                (dep := self.board.tasks.get(d)) and dep.status in terminal
                for d in task.depends_on
            ):
                return task
        return None

    # -- handoffs / reviews ------------------------------------------------ #
    def write_handoff(self, handoff: Handoff) -> Path:
        return artifacts.write_doc(
            self.artifact_dir / "handoffs" / f"{handoff.task_id}.md",
            handoff.model_dump(mode="json"),
            f"# Handoff {handoff.task_id}\n\n{handoff.summary_of_changes}\n\n"
            f"**Tests:** {handoff.test_result or 'n/a'}\n\n"
            f"**Next:** {handoff.next_recommendation}",
        )

    def write_review(self, review: Review, body: str) -> Path:
        return artifacts.write_doc(
            self.artifact_dir / "reviews" / f"{review.id}.md",
            review.model_dump(mode="json"),
            body,
        )

    def log(self, message: str) -> None:
        log_path = self.artifact_dir / "logs" / "plantod.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(f"{_now()} {message}\n")
