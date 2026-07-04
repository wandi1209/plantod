"""Run a task's test command and capture the result (PRD 12.E, FR-08)."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

_TIMEOUT_S = 600


@dataclass
class TestResult:
    ran: bool
    passed: bool
    command: str | None
    output: str = ""

    @property
    def summary(self) -> str:
        if not self.ran:
            return "no test command"
        return "passed" if self.passed else "failed"


def run_tests(command: str | None, root: Path, timeout: int = _TIMEOUT_S) -> TestResult:
    if not command:
        return TestResult(ran=False, passed=False, command=None)
    try:
        proc = subprocess.run(
            command, cwd=root, shell=True, capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return TestResult(ran=True, passed=False, command=command, output="TIMEOUT")
    except OSError as e:
        return TestResult(ran=True, passed=False, command=command, output=f"launch error: {e}")
    tail = (proc.stdout + proc.stderr)[-3000:]
    return TestResult(ran=True, passed=proc.returncode == 0, command=command, output=tail)
