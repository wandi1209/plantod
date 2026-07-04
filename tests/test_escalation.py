from plantod import executor, orchestrator
from plantod.repo import scan_repo
from plantod.schemas import Config, RiskLevel, Task, TaskEvent, TaskStatus
from plantod.state import StateManager


def _state(tmp_path) -> StateManager:
    state = StateManager(tmp_path)
    state.config = Config(
        planner_driver="mock", executor_driver="mock", reviewer_driver="mock",
        test_before_done=False, max_retries=2,
    )
    state.initialize()
    return state


def test_high_risk_task_escalates(tmp_path):
    state = _state(tmp_path)
    task = Task(id="T001", title="risky", objective="o", risk_level=RiskLevel.high, files_allowed=["*"])
    state.add_task(task)
    state.advance("T001", TaskEvent.activate)   # -> ready

    executor.run_task(state, task, scan_repo(state.root))
    assert state.get_task("T001").status is TaskStatus.needs_planner_review
    assert state.get_task("T001").escalation_count == 1


def test_replan_loop_terminates(tmp_path):
    state = _state(tmp_path)
    task = Task(id="T001", title="risky", objective="o", risk_level=RiskLevel.high, files_allowed=["*"])
    state.add_task(task)
    state.advance("T001", TaskEvent.activate)
    repo = scan_repo(state.root)

    # mock always escalates high-risk; loop must stop at the cap, not spin forever
    retries = 0
    for _ in range(20):
        executor.run_task(state, state.get_task("T001"), repo)
        if not orchestrator._try_replan(state, state.get_task("T001"), repo):
            break
        retries += 1
    assert retries <= state.config.max_retries + 1
    assert state.get_task("T001").status is TaskStatus.needs_planner_review
