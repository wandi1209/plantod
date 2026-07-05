from plantod import orchestrator
from plantod.schemas import Config, RoleBackend, TaskStatus, UsageEntry
from plantod.state import StateManager


def _state(tmp_path, **over) -> StateManager:
    state = StateManager(tmp_path)
    m = RoleBackend(provider="mock")
    state.config = Config(planner=m, executor=m, reviewer=m, test_before_done=False,
                          mode="auto", **over)
    state.initialize()
    return state


def test_max_tasks_per_run_stops_then_resume_finishes(tmp_path):
    state = _state(tmp_path, max_tasks_per_run=1)
    orchestrator.run_request(state, "add login")
    statuses = [t.status for t in state.board.tasks.values()]
    # only one task executed; the other still pending/ready
    assert any(s in (TaskStatus.done, TaskStatus.reviewed) for s in statuses)
    assert any(s in (TaskStatus.pending, TaskStatus.ready) for s in statuses)

    orchestrator.resume(state)
    done = {t.status for t in state.board.tasks.values()}
    assert done <= {TaskStatus.done, TaskStatus.reviewed}


def test_over_budget_stops(tmp_path):
    state = _state(tmp_path, max_tokens_budget=1)   # 1 token cap -> stops immediately
    orchestrator.run_request(state, "add login")
    # budget tripped before completing everything
    assert any(t.status in (TaskStatus.pending, TaskStatus.ready)
               for t in state.board.tasks.values())


def test_over_budget_helper(tmp_path):
    state = _state(tmp_path, max_tokens_budget=100)
    assert orchestrator._over_budget(state, "R001") is False
    state.board.usage.append(UsageEntry(role="planner", provider="mock",
                                        tokens_in=80, tokens_out=40, requirement_id="R001"))
    assert orchestrator._over_budget(state, "R001") is True


def test_unlimited_budget(tmp_path):
    state = _state(tmp_path)   # default max_tokens_budget=0
    state.board.usage.append(UsageEntry(role="planner", provider="mock",
                                        tokens_in=10**9, tokens_out=0, requirement_id="R001"))
    assert orchestrator._over_budget(state, "R001") is False
