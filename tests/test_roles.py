from __future__ import annotations

import pytest

from avalon.enums import Alignment, RoleType
from avalon.exceptions import ConfigurationError
from avalon.roles import (
    DEFAULT_ROLE_SET_BY_PLAYER_COUNT,
    ROLE_DEFINITIONS,
    is_minion,
    is_resistance,
    role_alignment,
    validate_role_selection,
)


def test_role_alignments_match_registry() -> None:
    expected = {
        RoleType.MERLIN: Alignment.RESISTANCE,
        RoleType.PERCIVAL: Alignment.RESISTANCE,
        RoleType.LOYAL_SERVANT: Alignment.RESISTANCE,
        RoleType.ASSASSIN: Alignment.MINION,
        RoleType.MORGANA: Alignment.MINION,
        RoleType.MORDRED: Alignment.MINION,
        RoleType.OBERON: Alignment.MINION,
        RoleType.MINION_OF_MORDRED: Alignment.MINION,
    }
    for role, alignment in expected.items():
        assert ROLE_DEFINITIONS[role].alignment is alignment
        assert role_alignment(role) is alignment
        if alignment is Alignment.RESISTANCE:
            assert is_resistance(role)
        else:
            assert is_minion(role)


@pytest.mark.parametrize("player_count", sorted(DEFAULT_ROLE_SET_BY_PLAYER_COUNT))
def test_default_roles_validate(player_count: int) -> None:
    roles = DEFAULT_ROLE_SET_BY_PLAYER_COUNT[player_count]
    validate_role_selection(player_count, roles)


def test_missing_assassin_rejected() -> None:
    roles = (
        RoleType.MERLIN,
        RoleType.PERCIVAL,
        RoleType.LOYAL_SERVANT,
        RoleType.MORGANA,
        RoleType.LOYAL_SERVANT,
    )
    with pytest.raises(ConfigurationError):
        validate_role_selection(5, roles)


def test_missing_merlin_with_percival_rejected() -> None:
    roles = (
        RoleType.PERCIVAL,
        RoleType.LOYAL_SERVANT,
        RoleType.ASSASSIN,
        RoleType.MORGANA,
        RoleType.LOYAL_SERVANT,
    )
    with pytest.raises(ConfigurationError):
        validate_role_selection(5, roles)


def test_duplicate_unique_role_rejected() -> None:
    roles = (
        RoleType.MERLIN,
        RoleType.MERLIN,
        RoleType.LOYAL_SERVANT,
        RoleType.ASSASSIN,
        RoleType.MORGANA,
    )
    with pytest.raises(ConfigurationError):
        validate_role_selection(5, roles)
