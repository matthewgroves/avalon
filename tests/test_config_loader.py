"""Tests for YAML configuration loader."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from avalon.config_loader import load_config_file
from avalon.enums import PlayerType, RoleType
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


def test_load_config_with_agent_players() -> None:
    """Load config with mix of human and agent players."""
    yaml_content = """
players:
  - Alice
  - name: AgentBob
    type: agent
  - name: AgentCarol
    type: agent
  - Dave
  - name: AgentEve
    type: agent

optional_roles:
  - mordred
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    try:
        setup = load_config_file(config_path)

        assert setup.game_config.player_count == 5
        assert len(setup.registrations) == 5

        # Check player types
        assert setup.registrations[0].display_name == "Alice"
        assert setup.registrations[0].player_type is PlayerType.HUMAN

        assert setup.registrations[1].display_name == "AgentBob"
        assert setup.registrations[1].player_type is PlayerType.AGENT

        assert setup.registrations[2].display_name == "AgentCarol"
        assert setup.registrations[2].player_type is PlayerType.AGENT

        assert setup.registrations[3].display_name == "Dave"
        assert setup.registrations[3].player_type is PlayerType.HUMAN

        assert setup.registrations[4].display_name == "AgentEve"
        assert setup.registrations[4].player_type is PlayerType.AGENT
    finally:
        Path(config_path).unlink()


def test_load_config_invalid_player_type() -> None:
    """Reject config with invalid player type."""
    yaml_content = """
players:
  - name: Alice
    type: robot

optional_roles: []
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    try:
        with pytest.raises(ConfigurationError, match="invalid type"):
            load_config_file(config_path)
    finally:
        Path(config_path).unlink()


def test_load_config_player_missing_name() -> None:
    """Reject config with player entry missing name field."""
    yaml_content = """
players:
  - type: agent

optional_roles: []
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    try:
        with pytest.raises(ConfigurationError, match="missing 'name'"):
            load_config_file(config_path)
    finally:
        Path(config_path).unlink()


def test_load_config_with_player_ids() -> None:
    """Player IDs are correctly extracted from structured player format."""
    yaml_content = """
players:
  - name: Alice
    id: alice_id
    type: human
  - name: Bob
    id: bob_id
  - Charlie
  - Dave
  - Eve

optional_roles: []
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    try:
        setup_config = load_config_file(config_path)
        registrations = setup_config.registrations

        # Alice has explicit ID and type
        assert registrations[0].display_name == "Alice"
        assert registrations[0].player_id == "alice_id"
        assert registrations[0].player_type == PlayerType.HUMAN

        # Bob has explicit ID, type defaults to human
        assert registrations[1].display_name == "Bob"
        assert registrations[1].player_id == "bob_id"
        assert registrations[1].player_type == PlayerType.HUMAN

        # Charlie uses simple format, no explicit ID
        assert registrations[2].display_name == "Charlie"
        assert registrations[2].player_id is None
        assert registrations[2].player_type == PlayerType.HUMAN
    finally:
        Path(config_path).unlink()


def test_load_config_invalid_player_id_type() -> None:
    """Reject config with non-string player ID."""
    yaml_content = """
players:
  - name: Alice
    id: 123

optional_roles: []
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    try:
        with pytest.raises(ConfigurationError, match="'id' must be a string"):
            load_config_file(config_path)
    finally:
        Path(config_path).unlink()
