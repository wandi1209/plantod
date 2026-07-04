"""Thin git helpers for change detection, diffing, and reverting (PRD 12.E guardrail)."""

from __future__ import annotations

import subprocess
from pathlib import Path

_TIMEOUT = 30


def _git(root: Path, *args: str, timeout: int = _TIMEOUT) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, timeout=timeout
    )


def is_git_repo(root: Path) -> bool:
    return (root / ".git").exists()


def changed_files(root: Path) -> set[str]:
    """Repo-relative paths of tracked-and-modified + untracked files."""
    try:
        out = _git(root, "status", "--porcelain", "--untracked-files=all")
    except (subprocess.SubprocessError, OSError):
        return set()
    files: set[str] = set()
    for line in out.stdout.splitlines():
        if not line.strip():
            continue
        path = line[3:]
        # rename: "old -> new"
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        files.add(path.strip().strip('"'))
    return files


def diff(root: Path, paths: list[str] | None = None) -> str:
    args = ["diff", "--no-color"]
    if paths:
        args += ["--", *paths]
    try:
        return _git(root, *args).stdout
    except (subprocess.SubprocessError, OSError):
        return ""


def revert(root: Path, paths: list[str]) -> list[str]:
    """Undo changes to the given paths. Tracked -> checkout; untracked -> delete.

    Returns the paths actually reverted. Best-effort; never raises.
    """
    reverted: list[str] = []
    for rel in paths:
        target = root / rel
        try:
            tracked = _git(root, "ls-files", "--error-unmatch", rel).returncode == 0
        except (subprocess.SubprocessError, OSError):
            tracked = False
        try:
            if tracked:
                _git(root, "checkout", "--", rel)
                reverted.append(rel)
            elif target.exists():
                if target.is_file():
                    target.unlink()
                    reverted.append(rel)
        except (subprocess.SubprocessError, OSError):
            continue
    return reverted
