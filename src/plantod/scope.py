"""Hard scope enforcement: keep executor edits inside the task's allowed files.

Trust-based prompting is not enough for production (PRD 12.E / 17). After an
executor runs, any file it changed outside `files_allowed` (or inside
`files_forbidden`) is reverted, and the task is escalated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path

from . import gitutil


@dataclass
class ScopeReport:
    changed: list[str] = field(default_factory=list)
    in_scope: list[str] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)
    reverted: list[str] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not self.violations


def _matches_any(path: str, patterns: list[str]) -> bool:
    return any(fnmatch(path, pat) for pat in patterns)


def is_allowed(path: str, allowed: list[str], forbidden: list[str]) -> bool:
    if forbidden and _matches_any(path, forbidden):
        return False
    if not allowed:
        return False              # empty allowlist = nothing permitted
    if "*" in allowed:            # wildcard = whole repo permitted
        return True
    return _matches_any(path, allowed)


def enforce(
    root: Path,
    changed: set[str],
    allowed: list[str],
    forbidden: list[str],
    revert_violations: bool = True,
) -> ScopeReport:
    """Classify changed files; revert out-of-scope ones (best-effort)."""
    report = ScopeReport(changed=sorted(changed))
    for rel in report.changed:
        # never touch plantod's own state dir
        if rel.startswith(".plantod/"):
            continue
        if is_allowed(rel, allowed, forbidden):
            report.in_scope.append(rel)
        else:
            report.violations.append(rel)
    if revert_violations and report.violations and gitutil.is_git_repo(root):
        report.reverted = gitutil.revert(root, report.violations)
    return report
