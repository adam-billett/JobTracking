"""
Configuration loading.

Reads config.yaml (settings; git-ignored) into a validated Settings
object. Per ARCHITECTURE.md this is treated as an adapter concern — it's
the boundary code that touches the disk — so the rest of the app receives
a plain validated object and never reads files itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class ConfigError(Exception):
    """Raised when configuration is missing or invalid."""


@dataclass(frozen=True)
class Settings:
    companies: list[str]  # Greenhouse board tokens, e.g. ["stripe", "anthropic"]
    database_path: str


def load_settings(config_path: Path) -> Settings:
    """
    Load and validate settings from a YAML file.

    Raises ConfigError with an actionable message if the file is missing or
    a required field is absent, so a misconfigured run fails clearly at
    startup rather than midway through.
    """
    if not config_path.exists():
        raise ConfigError(
            f"Config file not found at {config_path}. "
            "Copy config.example.yaml to config.yaml and fill it in."
        )

    with config_path.open(encoding="utf-8") as f:
        try:
            loaded = yaml.safe_load(f) or {}
        except yaml.YAMLError as exc:
            raise ConfigError(f"Config file {config_path} is not valid YAML: {exc}") from exc
    if not isinstance(loaded, dict):
        raise ConfigError(f"Config file {config_path} must contain a mapping at the top level.")
    raw: dict[str, Any] = loaded

    companies = raw.get("companies")
    if not isinstance(companies, list) or not companies:
        raise ConfigError("config.yaml must list at least one company under 'companies'.")
    if any(c is None or isinstance(c, dict) for c in companies):
        raise ConfigError("Company entries must be board tokens, not null or mappings.")

    database_path = raw.get("database_path", "data/jobs.db")

    return Settings(
        companies=[str(c) for c in companies],
        database_path=str(database_path),
    )
