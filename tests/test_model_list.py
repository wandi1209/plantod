import subprocess

from plantod.adapters import cliagent


def test_unknown_provider_returns_empty():
    assert cliagent.list_models("claude-code") == []   # no list command
    assert cliagent.list_models("mock") == []


def test_opencode_parsing(monkeypatch):
    monkeypatch.setattr(cliagent.shutil, "which", lambda _b: "/usr/bin/opencode")

    def fake_run(cmd, **kw):
        out = "anthropic/claude-3-5-sonnet\ndeepseek/deepseek-chat\n# header\nanthropic/claude-3-5-sonnet\n"
        return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")

    monkeypatch.setattr(cliagent.subprocess, "run", fake_run)
    models = cliagent.list_models("opencode")
    assert models == ["anthropic/claude-3-5-sonnet", "deepseek/deepseek-chat"]  # dedup + skip '#'


def test_nonzero_exit_returns_empty(monkeypatch):
    monkeypatch.setattr(cliagent.shutil, "which", lambda _b: "/usr/bin/opencode")
    monkeypatch.setattr(
        cliagent.subprocess, "run",
        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, stdout="", stderr="boom"),
    )
    assert cliagent.list_models("opencode") == []


def test_binary_missing_returns_empty(monkeypatch):
    monkeypatch.setattr(cliagent.shutil, "which", lambda _b: None)
    assert cliagent.list_models("opencode") == []
