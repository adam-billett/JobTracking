"""Unit tests for config loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from jobhunt.config.settings import ConfigError, load_settings


def test_malformed_yaml_raises_config_error(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text("companies: [unclosed\n", encoding="utf-8")  # invalid YAML
    with pytest.raises(ConfigError):
        load_settings(config)


def test_non_mapping_top_level_raises_config_error(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text("- just\n- a\n- list\n", encoding="utf-8")  # valid YAML, wrong shape
    with pytest.raises(ConfigError):
        load_settings(config)


def test_missing_file_raises_config_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_settings(tmp_path / "does-not-exist.yaml")


def test_valid_config_loads(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text("companies:\n  - stripe\ndatabase_path: data/jobs.db\n", encoding="utf-8")
    settings = load_settings(config)
    assert settings.companies == ["stripe"]
    assert settings.database_path == "data/jobs.db"
