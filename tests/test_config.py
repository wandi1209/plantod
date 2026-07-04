import pytest

from plantod.config import (
    config_path,
    default_config,
    global_config_path,
    load_config,
    save_config,
    update_role_backend,
)
from plantod.schemas import Config, RoleBackend


@pytest.fixture(autouse=True)
def _isolate_global(tmp_path, monkeypatch):
    # keep the real ~/.config/plantod out of tests
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))


def test_default_config_providers():
    cfg = default_config()
    assert cfg.planner.provider == "claude-code"
    assert cfg.executor.provider == "opencode"
    assert cfg.reviewer.provider == "claude-code"
    assert cfg.auto_run_small_tasks is True


def test_save_load_project_roundtrip(tmp_path):
    cfg = Config(executor=RoleBackend(provider="codex", model="o4"), auto_run_small_tasks=False)
    save_config(cfg, tmp_path)
    loaded = load_config(tmp_path)
    assert loaded.executor.provider == "codex"
    assert loaded.executor.model == "o4"
    assert loaded.auto_run_small_tasks is False


def test_global_then_project_override(tmp_path):
    # global sets planner=codex; project overrides executor only
    update_role_backend(global_config_path(), "planner", "codex", None)
    update_role_backend(config_path(tmp_path), "executor", "opencode", "deepseek")

    cfg = load_config(tmp_path)
    assert cfg.planner.provider == "codex"        # from global
    assert cfg.executor.provider == "opencode"    # from project
    assert cfg.executor.model == "deepseek"


def test_update_role_backend_preserves_other_keys(tmp_path):
    p = config_path(tmp_path)
    update_role_backend(p, "planner", "claude-code", None)
    update_role_backend(p, "executor", "opencode", None)
    cfg = load_config(tmp_path)
    assert cfg.planner.provider == "claude-code"
    assert cfg.executor.provider == "opencode"
