"""Artifact I/O: markdown + YAML frontmatter docs, and JSON state files (PRD 15, hybrid format)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_FRONTMATTER_DELIM = "---"


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
    path.write_text(content, encoding="utf-8")
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

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def read_json(path: Path) -> dict[str, Any]:
    import json

    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8") or "{}")
