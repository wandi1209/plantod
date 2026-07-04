from plantod import orchestrator
from plantod.schemas import Config, RoleBackend, TaskStatus
from plantod.state import StateManager


def _mock() -> Config:
    m = RoleBackend(provider="mock")
    return Config(planner=m, executor=m, reviewer=m, test_before_done=False)


def _mock_state(tmp_path) -> StateManager:
    state = StateManager(tmp_path)
    state.config = _mock()
    state.initialize()
    return state


def test_full_flow_offline(tmp_path):
    state = _mock_state(tmp_path)

    orchestrator.run_request(
        state,
        "add login feature",
        approval=lambda _t: True,
        auto_review=True,
    )

    # tasks generated + persisted
    assert len(state.board.tasks) == 2
    assert (state.artifact_dir / "tasks" / "T001.md").exists()

    # handoffs written for both tasks
    assert (state.artifact_dir / "handoffs" / "T001.md").exists()
    assert (state.artifact_dir / "handoffs" / "T002.md").exists()

    # both tasks reach a terminal state after review
    statuses = {t.status for t in state.board.tasks.values()}
    assert statuses <= {TaskStatus.reviewed, TaskStatus.done}

    # review artifact written
    reviews = list((state.artifact_dir / "reviews").glob("*.md"))
    assert reviews, "expected a review artifact"


def test_board_persisted_and_reloadable(tmp_path):
    state = _mock_state(tmp_path)
    orchestrator.run_request(state, "add search", approval=lambda _t: True)

    reloaded = StateManager(tmp_path)
    assert len(reloaded.board.tasks) == len(state.board.tasks)
    assert reloaded.session.current_requirement_id == "R001"
