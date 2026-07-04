"""Repository detection, structure scan, and test-command discovery (PRD 12.A, FR-01)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

# Directories never worth scanning for context.
_IGNORE_DIRS = {
    ".git", ".plantod", "__pycache__", "node_modules", ".venv", "venv",
    ".mypy_cache", ".pytest_cache", "dist", "build", ".idea", ".vscode",
}


@dataclass
class RepoContext:
    root: Path
    is_git: bool
    files: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    test_command: str | None = None

    def summary(self, max_files: int = 60) -> str:
        head = "\n".join(self.files[:max_files])
        more = "" if len(self.files) <= max_files else f"\n... (+{len(self.files) - max_files} more)"
        langs = ", ".join(self.languages) or "unknown"
        return (
            f"root: {self.root}\n"
            f"git: {self.is_git}\n"
            f"languages: {langs}\n"
            f"test_command: {self.test_command or 'none'}\n"
            f"files:\n{head}{more}"
        )


_LANG_BY_EXT = {
    ".py": "python", ".js": "javascript", ".ts": "typescript", ".tsx": "typescript",
    ".go": "go", ".rs": "rust", ".rb": "ruby", ".java": "java", ".php": "php",
    ".xml": "xml", ".yaml": "yaml", ".yml": "yaml",
}


def is_git_repo(root: Path) -> bool:
    return (root / ".git").exists()


def _discover_test_command(root: Path, files: set[str]) -> str | None:
    """Best-effort test command discovery across common project types (PRD 23 risk)."""
    if (root / "pyproject.toml").exists() or (root / "pytest.ini").exists() or any(
        f.startswith("tests/") or "/tests/" in f for f in files
    ):
        return "pytest"
    if (root / "package.json").exists():
        try:
            pkg = json.loads((root / "package.json").read_text(encoding="utf-8"))
            if "test" in pkg.get("scripts", {}):
                return "npm test"
        except (json.JSONDecodeError, OSError):
            pass
    if (root / "go.mod").exists():
        return "go test ./..."
    if (root / "Cargo.toml").exists():
        return "cargo test"
    # Odoo / custom addon (PRD Use Case 4)
    if any(f.endswith("__manifest__.py") for f in files):
        return None  # odoo test invocation is project-specific
    return None


def scan_repo(root: Path | str = ".", max_files: int = 400) -> RepoContext:
    root = Path(root).resolve()
    files: list[str] = []
    exts: set[str] = set()
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel_parts = path.relative_to(root).parts
        if any(part in _IGNORE_DIRS for part in rel_parts):
            continue
        rel = "/".join(rel_parts)
        files.append(rel)
        exts.add(path.suffix)
        if len(files) >= max_files:
            break
    files.sort()
    languages = sorted({_LANG_BY_EXT[e] for e in exts if e in _LANG_BY_EXT})
    return RepoContext(
        root=root,
        is_git=is_git_repo(root),
        files=files,
        languages=languages,
        test_command=_discover_test_command(root, set(files)),
    )
