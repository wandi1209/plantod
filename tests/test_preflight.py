from plantod import preflight
from plantod.schemas import Config, RoleBackend


def test_mock_always_ok():
    m = RoleBackend(provider="mock")
    cfg = Config(planner=m, executor=m, reviewer=m)
    assert preflight.missing(cfg) == []
    assert all(r["ok"] for r in preflight.check_providers(cfg))


def test_missing_binary_flagged(monkeypatch):
    monkeypatch.setattr(preflight.shutil, "which", lambda _b: None)
    cfg = Config(planner=RoleBackend(provider="claude-code"))
    miss = preflight.missing(cfg)
    roles = {m["role"] for m in miss}
    assert "planner" in roles
    assert all(m["binary"] for m in miss)


def test_present_binary_ok(monkeypatch):
    monkeypatch.setattr(preflight.shutil, "which", lambda _b: "/usr/bin/" + _b)
    cfg = Config(planner=RoleBackend(provider="claude-code"))
    assert not [m for m in preflight.missing(cfg) if m["role"] == "planner"]
