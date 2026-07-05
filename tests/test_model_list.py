import subprocess

from plantod.adapters import cliagent

_FAKE = (
    "opencode/claude-opus-4-8\n"
    "opencode/deepseek-v4-flash\n"
    "opencode-go/kimi-k2.7-code\n"
    "opencode-go/qwen3.7-max\n"
    "# a header line\n"
    "opencode/claude-opus-4-8\n"   # duplicate
)


def _patch(monkeypatch):
    monkeypatch.setattr(cliagent.shutil, "which", lambda _b: "/usr/bin/opencode")
    monkeypatch.setattr(
        cliagent.subprocess, "run",
        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, stdout=_FAKE, stderr=""),
    )


def test_unknown_provider_returns_empty():
    assert cliagent.list_models("claude-code") == []
    assert cliagent.list_models("mock") == []


def test_opencode_lists_only_opencode_prefix(monkeypatch):
    _patch(monkeypatch)
    models = cliagent.list_models("opencode")
    assert models == ["opencode/claude-opus-4-8", "opencode/deepseek-v4-flash"]
    assert all(m.startswith("opencode/") for m in models)


def test_opencode_go_lists_only_go_prefix(monkeypatch):
    _patch(monkeypatch)
    models = cliagent.list_models("opencode-go")
    assert models == ["opencode-go/kimi-k2.7-code", "opencode-go/qwen3.7-max"]
    assert not any(m.startswith("opencode/") for m in models)


def test_nonzero_exit_returns_empty(monkeypatch):
    monkeypatch.setattr(cliagent.shutil, "which", lambda _b: "/usr/bin/opencode")
    monkeypatch.setattr(
        cliagent.subprocess, "run",
        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, stdout="", stderr="boom"),
    )
    assert cliagent.list_models("opencode-go") == []


def test_binary_missing_returns_empty(monkeypatch):
    monkeypatch.setattr(cliagent.shutil, "which", lambda _b: None)
    assert cliagent.list_models("opencode") == []
