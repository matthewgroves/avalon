from __future__ import annotations

import pytest

from avalon.config import TEAM_SIZE_TABLE, GameConfig, MissionConfig
from avalon.discussion import DiscussionConfig
from avalon.enums import RoleType
from avalon.exceptions import ConfigurationError


@pytest.mark.parametrize("player_count", sorted(TEAM_SIZE_TABLE))
def test_mission_config_matches_reference_table(player_count: int) -> None:
    mission_config = MissionConfig.for_player_count(player_count)
    assert mission_config.team_sizes == TEAM_SIZE_TABLE[player_count]
    expected_fail = 2 if player_count >= 7 else 1
    assert mission_config.required_fail_counts == (1, 1, 1, expected_fail, 1)


def test_game_config_default_roles_validate() -> None:
    config = GameConfig.default(7)
    assert config.player_count == 7
    assert len(config.roles) == 7
    assert config.mission_config.team_sizes == TEAM_SIZE_TABLE[7]
    assert config.alignment_counts == (4, 3)


def test_game_config_rejects_invalid_role_counts() -> None:
    roles = (
        RoleType.MERLIN,
        RoleType.PERCIVAL,
        RoleType.LOYAL_SERVANT,
        RoleType.ASSASSIN,
        RoleType.MORGANA,
    )
    with pytest.raises(ConfigurationError):
        GameConfig(player_count=6, roles=roles)


def test_game_config_has_discussion_config() -> None:
    """Test that GameConfig includes discussion configuration."""
    config = GameConfig.default(5)
    assert hasattr(config, "discussion_config")
    assert isinstance(config.discussion_config, DiscussionConfig)
    assert config.discussion_config.enabled is True


def test_game_config_custom_discussion_config() -> None:
    """Test GameConfig with custom discussion configuration."""
    custom_discussion = DiscussionConfig(
        enabled=False,
        pre_proposal_enabled=False,
        max_statements_per_phase=1,
    )
    config = GameConfig.default(5)
    config_with_custom = GameConfig(
        player_count=config.player_count,
        roles=config.roles,
        discussion_config=custom_discussion,
    )
    assert config_with_custom.discussion_config.enabled is False
    assert config_with_custom.discussion_config.pre_proposal_enabled is False
    assert config_with_custom.discussion_config.max_statements_per_phase == 1
