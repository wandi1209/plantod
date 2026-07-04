import pytest

from plantod.schemas import IllegalTransition, TaskEvent, TaskStatus, next_status


def test_happy_path():
    s = TaskStatus.pending
    for ev, expect in [
        (TaskEvent.activate, TaskStatus.ready),
        (TaskEvent.start, TaskStatus.in_progress),
        (TaskEvent.submit_test, TaskStatus.testing),
        (TaskEvent.pass_test, TaskStatus.done),
        (TaskEvent.review, TaskStatus.reviewed),
    ]:
        s = next_status(s, ev)
        assert s is expect


def test_block_escalate_resolve():
    s = TaskStatus.in_progress
    s = next_status(s, TaskEvent.block)
    assert s is TaskStatus.blocked
    s = next_status(s, TaskEvent.escalate)
    assert s is TaskStatus.needs_planner_review
    s = next_status(s, TaskEvent.resolve)
    assert s is TaskStatus.ready


def test_fail_test_loops_back():
    assert next_status(TaskStatus.testing, TaskEvent.fail_test) is TaskStatus.in_progress


def test_illegal_transition():
    with pytest.raises(IllegalTransition):
        next_status(TaskStatus.pending, TaskEvent.pass_test)


def test_cancel_from_active_but_not_terminal():
    assert next_status(TaskStatus.ready, TaskEvent.cancel) is TaskStatus.cancelled
    with pytest.raises(IllegalTransition):
        next_status(TaskStatus.reviewed, TaskEvent.cancel)
