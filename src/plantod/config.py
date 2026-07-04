"""Load, save, and default the per-project config.yaml (PRD 19.1)."""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from .schemas import Config

CONFIG_FILENAME = "config.yaml"


def load_dotenv(root: Path | str = ".") -> None:
    """Load KEY=VALUE lines from a local .env into os.environ (no external dep).

    Existing environment variables win; malformed lines are skipped.
    """
    path = Path(root) / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def default_config() -> Config:
    return Config()


def config_path(artifact_dir: Path) -> Path:
    return artifact_dir / CONFIG_FILENAME


def save_config(cfg: Config, artifact_dir: Path) -> Path:
    path = config_path(artifact_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(cfg.model_dump(), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return path


def load_config(artifact_dir: Path) -> Config:
    path = config_path(artifact_dir)
    if not path.exists():
        return default_config()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return Config(**data)
