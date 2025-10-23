"""Tests for YAML configuration loader."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from avalon.config_loader import load_config_file
from avalon.enums import RoleType
from avalon.exceptions import ConfigurationError
from avalon.interaction import BriefingDeliveryMode


def test_load_config_with_mordred_only() -> None:
    """Load config file with 5 players and only Mordred as optional role."""
    yaml_content = """
players:
  - a
  - b
  - c
  - d
  - e

optional_roles:
  - mordred

briefing:
  mode: sequential
  pause_before_each: false
  pause_after_each: false
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    try:
        setup = load_config_file(config_path)

        assert setup.game_config.player_count == 5
        assert len(setup.registrations) == 5
        assert [r.display_name for r in setup.registrations] == ["a", "b", "c", "d", "e"]

        roles = setup.game_config.roles
        assert roles.count(RoleType.MERLIN) == 1
        assert roles.count(RoleType.ASSASSIN) == 1
        assert roles.count(RoleType.MORDRED) == 1
        assert roles.count(RoleType.LOYAL_SERVANT) == 2
        assert roles.count(RoleType.MINION_OF_MORDRED) == 0

        assert setup.briefing_options.mode is BriefingDeliveryMode.SEQUENTIAL
        assert not setup.briefing_options.pause_before_each
        assert not setup.briefing_options.pause_after_each
    finally:
        Path(config_path).unlink()


def test_load_config_with_multiple_optional_roles() -> None:
    """Load config with multiple optional roles."""
    yaml_content = """
players:
  - Alice
  - Bob
  - Carol
  - Dave
  - Eve
  - Frank
  - Grace

optional_roles:
  - percival
  - morgana
  - mordred

briefing:
  mode: batch
  pause_before_each: true
  pause_after_each: true

random_seed: 42
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    try:
        setup = load_config_file(config_path)

        assert setup.game_config.player_count == 7
        assert setup.game_config.random_seed == 42

        roles = setup.game_config.roles
        assert roles.count(RoleType.MERLIN) == 1
        assert roles.count(RoleType.PERCIVAL) == 1
        assert roles.count(RoleType.ASSASSIN) == 1
        assert roles.count(RoleType.MORGANA) == 1
        assert roles.count(RoleType.MORDRED) == 1

        assert setup.briefing_options.mode is BriefingDeliveryMode.BATCH
        assert setup.briefing_options.pause_before_each
        assert setup.briefing_options.pause_after_each
    finally:
        Path(config_path).unlink()


def test_load_config_missing_players() -> None:
    """Reject config without players list."""
    yaml_content = """
optional_roles:
  - mordred
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    try:
        with pytest.raises(ConfigurationError, match="must specify 'players'"):
            load_config_file(config_path)
    finally:
        Path(config_path).unlink()


def test_load_config_invalid_role() -> None:
    """Reject config with unknown role type."""
    yaml_content = """
players:
  - a
  - b
  - c
  - d
  - e

optional_roles:
  - invalid_role
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    try:
        with pytest.raises(ConfigurationError, match="Unknown role type"):
            load_config_file(config_path)
    finally:
        Path(config_path).unlink()


def test_load_config_file_not_found() -> None:
    """Raise FileNotFoundError for missing config file."""
    with pytest.raises(FileNotFoundError):
        load_config_file("/nonexistent/config.yaml")
