"""Config loading with global + per-project override (PRD 19.1, NFR-02).

Precedence (low -> high): built-in defaults < global (~/.config/plantod/config.yaml)
< project (.plantod/config.yaml). `plantod login` writes the global scope by default.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from .schemas import Config

CONFIG_FILENAME = "config.yaml"


# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
def global_config_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "plantod" / CONFIG_FILENAME


def config_path(artifact_dir: Path) -> Path:
    return artifact_dir / CONFIG_FILENAME


# --------------------------------------------------------------------------- #
# Raw read/write + merge
# --------------------------------------------------------------------------- #
def _read_raw(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _write_raw(path: Path, data: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    return path


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def default_config() -> Config:
    return Config()


def load_config(artifact_dir: Path) -> Config:
    """Merge global then project config over defaults."""
    merged = _deep_merge(_read_raw(global_config_path()), _read_raw(config_path(artifact_dir)))
    return Config(**merged) if merged else Config()


def load_global_config() -> Config:
    raw = _read_raw(global_config_path())
    return Config(**raw) if raw else Config()


def save_config(cfg: Config, artifact_dir: Path) -> Path:
    """Persist a full Config to the project scope."""
    return _write_raw(config_path(artifact_dir), cfg.model_dump(mode="json"))


def save_global_config(cfg: Config) -> Path:
    return _write_raw(global_config_path(), cfg.model_dump(mode="json"))


def update_role_backend(
    scope_path: Path, role: str, provider: str, model: str | None
) -> dict[str, Any]:
    """Set one role's provider/model in the given scope file, preserving other keys."""
    raw = _read_raw(scope_path)
    raw[role] = {"provider": provider, "model": model}
    _write_raw(scope_path, raw)
    return raw


def update_value(scope_path: Path, key: str, value: Any) -> dict[str, Any]:
    """Set a single top-level config key in the given scope file."""
    raw = _read_raw(scope_path)
    raw[key] = value
    _write_raw(scope_path, raw)
    return raw


# --------------------------------------------------------------------------- #
# .env auto-load (kept for provider CLIs that read env vars)
# --------------------------------------------------------------------------- #
def load_dotenv(root: Path | str = ".") -> None:
    """Load KEY=VALUE lines from a local .env into os.environ (no external dep)."""
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
