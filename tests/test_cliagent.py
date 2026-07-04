import pytest

from plantod.adapters.cliagent import CliAgent, provider_binary
from plantod.adapters.registry import resolve
from plantod.schemas import Config, Role, RoleBackend


def test_argv_shapes():
    assert CliAgent("claude-code").spec.argv("hi", None) == ["claude", "-p", "hi"]
    assert CliAgent("claude-code", "opus").spec.argv("hi", "opus") == ["claude", "-p", "hi", "--model", "opus"]
    assert CliAgent("codex").spec.argv("hi", None) == ["codex", "exec", "hi"]
    assert CliAgent("codex", "o4").spec.argv("hi", "o4") == ["codex", "exec", "--model", "o4", "hi"]
    # opencode selects a read-only 'plan' agent by default
    assert CliAgent("opencode").spec.argv("hi", None) == ["opencode", "run", "--agent", "plan", "hi"]


def test_argv_opencode_edit_uses_build_agent():
    # executor (edit=True) uses the build agent; read-only roles use plan
    assert CliAgent("opencode", "m").spec.argv("hi", "m", edit=True) == [
        "opencode", "run", "--agent", "build", "--model", "m", "hi"
    ]
    assert CliAgent("opencode").spec.argv("hi", None, edit=False)[3] == "plan"


def test_unknown_provider():
    with pytest.raises(ValueError):
        CliAgent("gpt-9000")


def test_provider_binary():
    assert provider_binary("claude-code") == "claude"
    assert provider_binary("codex") == "codex"
    assert provider_binary("opencode") == "opencode"
    assert provider_binary("mock") is None


def test_registry_resolves_cliagent():
    cfg = Config(executor=RoleBackend(provider="codex", model="o4"))
    adapter = resolve(Role.executor, cfg)
    assert isinstance(adapter, CliAgent)
    assert adapter.name == "codex"
    assert adapter.model == "o4"


def test_registry_resolves_mock():
    from plantod.adapters.mock import MockAdapter

    cfg = Config(planner=RoleBackend(provider="mock"))
    assert isinstance(resolve(Role.planner, cfg), MockAdapter)
