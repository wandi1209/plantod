"""Artifact I/O: markdown + YAML frontmatter docs, and JSON state files (PRD 15, hybrid format)."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

import yaml

_FRONTMATTER_DELIM = "---"


def _atomic_write(path: Path, text: str) -> None:
    """Write via temp file + os.replace so a crash never leaves a half file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=path.suffix)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


# --------------------------------------------------------------------------- #
# Local project scaffold (PRD 15)
# --------------------------------------------------------------------------- #
ARTIFACT_SUBDIRS = ("requirements", "plans", "tasks", "handoffs", "reviews", "logs")


def scaffold(artifact_dir: Path) -> None:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    for sub in ARTIFACT_SUBDIRS:
        (artifact_dir / sub).mkdir(exist_ok=True)


# --------------------------------------------------------------------------- #
# Markdown + YAML frontmatter
# --------------------------------------------------------------------------- #
def write_doc(path: Path, frontmatter: dict[str, Any], body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fm = yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True).strip()
    content = f"{_FRONTMATTER_DELIM}\n{fm}\n{_FRONTMATTER_DELIM}\n\n{body.strip()}\n"
    _atomic_write(path, content)
    return path


def read_doc(path: Path) -> tuple[dict[str, Any], str]:
    """Return (frontmatter, body). Tolerates docs without frontmatter."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith(_FRONTMATTER_DELIM):
        return {}, text
    parts = text.split(_FRONTMATTER_DELIM, 2)
    # parts == ["", "<yaml>", "<body>"]
    if len(parts) < 3:
        return {}, text
    frontmatter = yaml.safe_load(parts[1]) or {}
    return frontmatter, parts[2].lstrip("\n")


# --------------------------------------------------------------------------- #
# JSON state
# --------------------------------------------------------------------------- #
def write_json(path: Path, data: dict[str, Any]) -> Path:
    import json

    _atomic_write(path, json.dumps(data, indent=2, ensure_ascii=False))
    return path


def read_json(path: Path) -> dict[str, Any]:
    import json

    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8") or "{}")
