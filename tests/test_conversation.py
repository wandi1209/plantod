from plantod import conversation, orchestrator
from plantod.schemas import Config, RoleBackend
from plantod.state import StateManager


def _state(tmp_path) -> StateManager:
    state = StateManager(tmp_path)
    m = RoleBackend(provider="mock")
    state.config = Config(planner=m, executor=m, reviewer=m, test_before_done=False)
    state.initialize()
    return state


def test_record_and_build_context(tmp_path):
    state = _state(tmp_path)
    conversation.record(state, "user", "add login")
    conversation.record(state, "plantod", "planned login")
    ctx = conversation.build_context(state)
    assert "user: add login" in ctx
    assert "plantod: planned login" in ctx


def test_record_trims_to_max(tmp_path):
    state = _state(tmp_path)
    for i in range(conversation.MAX_TURNS + 10):
        conversation.record(state, "user", f"msg {i}")
    assert len(state.session.turns) == conversation.MAX_TURNS
    assert state.session.turns[-1].text == f"msg {conversation.MAX_TURNS + 9}"


def test_context_limited_to_n(tmp_path):
    state = _state(tmp_path)
    for i in range(10):
        conversation.record(state, "user", f"m{i}")
    ctx = conversation.build_context(state, n=3)
    assert ctx.count("\n") == 2          # 3 lines
    assert "m9" in ctx and "m0" not in ctx


def test_turns_persist_across_reload(tmp_path):
    state = _state(tmp_path)
    conversation.record(state, "user", "remember me")
    state.save()
    reloaded = StateManager(tmp_path)
    assert reloaded.session.turns[-1].text == "remember me"


def test_followup_keeps_original_request(tmp_path):
    state = _state(tmp_path)
    orchestrator.run_request(state, "add login", approval=lambda _t: True, context="")
    conversation.record(state, "user", "add login")
    ctx = conversation.build_context(state)
    orchestrator.run_request(state, "now add logout", approval=lambda _t: True, context=ctx)
    # requirements store original requests, not the augmented context blob
    reqs = {r.request for r in state.board.requirements.values()}
    assert reqs == {"add login", "now add logout"}
