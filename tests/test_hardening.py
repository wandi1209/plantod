import pytest

from plantod.config import load_dotenv
from plantod.locking import LockBusy, project_lock
from plantod.planner import PlanValidationError, validate_dependencies
from plantod.schemas import Task


def _task(tid, deps=None):
    return Task(id=tid, title=tid, objective="o", depends_on=deps or [])


def test_unknown_dependency():
    with pytest.raises(PlanValidationError):
        validate_dependencies([_task("T001", ["T999"])])


def test_dependency_cycle():
    with pytest.raises(PlanValidationError):
        validate_dependencies([_task("A", ["B"]), _task("B", ["A"])])


def test_valid_dag_ok():
    validate_dependencies([_task("A"), _task("B", ["A"]), _task("C", ["A", "B"])])


def test_lock_is_exclusive(tmp_path):
    with project_lock(tmp_path):
        with pytest.raises(LockBusy):
            with project_lock(tmp_path):
                pass


def test_lock_released_after_exit(tmp_path):
    with project_lock(tmp_path):
        pass
    # re-acquire fine
    with project_lock(tmp_path):
        pass


def test_load_dotenv(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text('FOO=bar\n# comment\nBAZ="q q"\n')
    monkeypatch.delenv("FOO", raising=False)
    monkeypatch.delenv("BAZ", raising=False)
    load_dotenv(tmp_path)
    import os

    assert os.environ["FOO"] == "bar"
    assert os.environ["BAZ"] == "q q"


def test_atomic_write(tmp_path):
    from plantod.artifacts import read_json, write_json

    p = tmp_path / "s.json"
    write_json(p, {"a": 1})
    write_json(p, {"a": 2})            # overwrite via temp+rename
    assert read_json(p) == {"a": 2}
    # no stray temp files left behind
    assert not list(tmp_path.glob(".tmp-*"))
