from plantod import orchestrator
from plantod.schemas import Config, RiskLevel, RoleBackend, Task, TaskStatus
from plantod.state import StateManager


def _state(tmp_path, mode: str) -> StateManager:
    state = StateManager(tmp_path)
    m = RoleBackend(provider="mock")
    state.config = Config(planner=m, executor=m, reviewer=m, test_before_done=False, mode=mode)
    state.initialize()
    return state


def _gated_task() -> Task:
    # medium risk + wildcard scope + no test => gated in approval mode
    return Task(id="T001", title="x", objective="o", risk_level=RiskLevel.medium, files_allowed=["*"])


def test_approval_mode_gates_task(tmp_path):
    state = _state(tmp_path, "approval")
    assert orchestrator.should_auto_run(_gated_task(), state.config) is False


def test_auto_mode_runs_everything(tmp_path):
    state = _state(tmp_path, "auto")
    assert orchestrator.should_auto_run(_gated_task(), state.config) is True


def test_auto_mode_runs_to_review_without_flag(tmp_path):
    state = _state(tmp_path, "auto")
    # no approval callback, no auto_review flag -> auto mode still reviews to done
    orchestrator.run_request(state, "add login")
    statuses = {t.status for t in state.board.tasks.values()}
    assert statuses <= {TaskStatus.reviewed, TaskStatus.done}
    assert statuses  # tasks exist
    assert list((state.artifact_dir / "reviews").glob("*.md")), "auto mode should have reviewed"


def test_approval_mode_stops_at_gate(tmp_path):
    state = _state(tmp_path, "approval")
    # default approval denies -> gated tasks not completed
    orchestrator.run_request(state, "add login")
    # mock plan: T001 low (auto-runs), T002 medium+wildcard (gated, denied) -> not reviewed
    t2 = state.get_task("T002")
    assert t2 is not None and t2.status is not TaskStatus.reviewed
