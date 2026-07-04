from plantod.config import default_config, load_config, save_config
from plantod.schemas import Config


def test_default_config():
    cfg = default_config()
    assert cfg.planner and cfg.executor and cfg.reviewer
    assert cfg.auto_run_small_tasks is True


def test_save_load_roundtrip(tmp_path):
    cfg = Config(executor_driver="mock", auto_run_small_tasks=False)
    save_config(cfg, tmp_path)
    loaded = load_config(tmp_path)
    assert loaded.executor_driver == "mock"
    assert loaded.auto_run_small_tasks is False


def test_load_missing_returns_default(tmp_path):
    loaded = load_config(tmp_path / "nope")
    assert loaded.executor_driver == default_config().executor_driver
