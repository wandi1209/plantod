from plantod import orchestrator, usage
from plantod.schemas import Config, RoleBackend, UsageEntry
from plantod.state import StateManager


def test_estimate_tokens():
    assert usage.estimate_tokens("") == 0
    assert usage.estimate_tokens("abcd") == 1
    assert usage.estimate_tokens("a" * 400) == 100


def test_summarize():
    entries = [
        UsageEntry(role="planner", provider="mock", tokens_in=10, tokens_out=5),
        UsageEntry(role="executor", provider="mock", tokens_in=20, tokens_out=8),
    ]
    agg = usage.summarize(entries)
    assert agg["mock"] == {"in": 30, "out": 13, "calls": 2}


def test_estimate_cost():
    entries = [UsageEntry(role="planner", provider="claude-code", tokens_in=1_000_000, tokens_out=1_000_000)]
    cfg = Config(prices={"claude-code": [15.0, 75.0]})
    assert usage.estimate_cost(entries, cfg) == 90.0
    assert usage.estimate_cost(entries, Config()) is None   # no prices -> None


def test_flow_records_usage(tmp_path):
    state = StateManager(tmp_path)
    m = RoleBackend(provider="mock")
    state.config = Config(planner=m, executor=m, reviewer=m, test_before_done=False)
    state.initialize()

    orchestrator.run_request(state, "add login", approval=lambda _t: True, auto_review=True)

    assert state.board.usage, "expected usage entries recorded"
    roles = {e.role for e in state.board.usage}
    assert {"planner", "executor", "reviewer"} <= roles
    assert all(e.provider == "mock" for e in state.board.usage)
    assert sum(e.tokens_in + e.tokens_out for e in state.board.usage) > 0
