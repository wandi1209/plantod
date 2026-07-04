"""Load, save, and default the per-project config.yaml (PRD 19.1)."""

from __future__ import annotations

from pathlib import Path

import yaml

from .schemas import Config

CONFIG_FILENAME = "config.yaml"


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
