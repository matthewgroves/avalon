from __future__ import annotations

import pytest

from avalon.config import GameConfig
from avalon.enums import PlayerType, RoleType
from avalon.exceptions import ConfigurationError
from avalon.setup import PlayerRegistration, perform_setup


def _names(count: int) -> list[str]:
    return [f"Player {index}" for index in range(1, count + 1)]


def test_setup_deterministic_with_seed() -> None:
    config = GameConfig.default(5)
    registrations = [PlayerRegistration(name) for name in _names(5)]

    result_one = perform_setup(config, registrations, seed=42)
    result_two = perform_setup(config, registrations, seed=42)

    roles_one = [player.role for player in result_one.players]
    roles_two = [player.role for player in result_two.players]
    assert roles_one == roles_two
    assert result_one.public_lobby == tuple(_names(5))
    assert result_one.seed == 42


def test_merlin_briefing_excludes_mordred() -> None:
    config = GameConfig.default(7)
    registrations = [PlayerRegistration(name) for name in _names(7)]

    result = perform_setup(config, registrations, seed=7)
    players_by_id = {player.player_id: player for player in result.players}

    merlin_player = next(player for player in result.players if player.role is RoleType.MERLIN)
    packet = result.knowledge_for(merlin_player.player_id)
    visible_roles = {players_by_id[player_id].role for player_id in packet.visible_player_ids}

    assert RoleType.MORDRED not in visible_roles
    assert RoleType.ASSASSIN in visible_roles
    assert RoleType.MORGANA in visible_roles


def test_duplicate_names_rejected() -> None:
    config = GameConfig.default(5)
    registrations = [
        PlayerRegistration("Alice"),
        PlayerRegistration("Bob"),
        PlayerRegistration("alice"),
        PlayerRegistration("Charlie"),
        PlayerRegistration("Diana"),
    ]

    with pytest.raises(ConfigurationError):
        perform_setup(config, registrations)


def test_player_type_flows_through_setup() -> None:
    """Verify player_type from registration is preserved in Player objects."""
    config = GameConfig.default(5)
    registrations = [
        PlayerRegistration("Alice", player_type=PlayerType.HUMAN),
        PlayerRegistration("AgentBob", player_type=PlayerType.AGENT),
        PlayerRegistration("Carol", player_type=PlayerType.HUMAN),
        PlayerRegistration("AgentDave", player_type=PlayerType.AGENT),
        PlayerRegistration("AgentEve", player_type=PlayerType.AGENT),
    ]

    result = perform_setup(config, registrations, seed=10)

    assert result.players[0].display_name == "Alice"
    assert result.players[0].player_type is PlayerType.HUMAN
    assert result.players[0].is_human
    assert not result.players[0].is_agent

    assert result.players[1].display_name == "AgentBob"
    assert result.players[1].player_type is PlayerType.AGENT
    assert result.players[1].is_agent
    assert not result.players[1].is_human

    assert result.players[2].player_type is PlayerType.HUMAN
    assert result.players[3].player_type is PlayerType.AGENT
    assert result.players[4].player_type is PlayerType.AGENT
