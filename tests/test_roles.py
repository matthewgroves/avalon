from __future__ import annotations

import pytest

from avalon.enums import Alignment, RoleType
from avalon.exceptions import ConfigurationError
from avalon.roles import (
    DEFAULT_ROLE_SET_BY_PLAYER_COUNT,
    ROLE_DEFINITIONS,
    build_role_list,
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


def test_build_role_list_with_no_optional_roles() -> None:
    """Build role list with only essentials (Merlin + Assassin) fills rest with generics."""
    roles = build_role_list(5, optional_roles=None)
    assert len(roles) == 5
    assert roles.count(RoleType.MERLIN) == 1
    assert roles.count(RoleType.ASSASSIN) == 1
    assert roles.count(RoleType.LOYAL_SERVANT) == 2
    assert roles.count(RoleType.MINION_OF_MORDRED) == 1


def test_build_role_list_with_mordred_only() -> None:
    """Build 5-player game with only Mordred as optional special character."""
    roles = build_role_list(5, optional_roles=[RoleType.MORDRED])
    assert len(roles) == 5
    assert roles.count(RoleType.MERLIN) == 1
    assert roles.count(RoleType.ASSASSIN) == 1
    assert roles.count(RoleType.MORDRED) == 1
    assert roles.count(RoleType.LOYAL_SERVANT) == 2
    assert roles.count(RoleType.MINION_OF_MORDRED) == 0


def test_build_role_list_with_multiple_optional() -> None:
    """Build 7-player game with Percival, Morgana, and Mordred."""
    roles = build_role_list(
        7, optional_roles=[RoleType.PERCIVAL, RoleType.MORGANA, RoleType.MORDRED]
    )
    assert len(roles) == 7
    assert roles.count(RoleType.MERLIN) == 1
    assert roles.count(RoleType.PERCIVAL) == 1
    assert roles.count(RoleType.ASSASSIN) == 1
    assert roles.count(RoleType.MORGANA) == 1
    assert roles.count(RoleType.MORDRED) == 1
    # 4 resistance (Merlin, Percival, 2 servants), 3 minions (Assassin, Morgana, Mordred)
    assert roles.count(RoleType.LOYAL_SERVANT) == 2
    assert roles.count(RoleType.MINION_OF_MORDRED) == 0


def test_build_role_list_validates_result() -> None:
    """Ensure build_role_list produces valid role selections."""
    # Test various player counts with different optional role combinations
    roles_5 = build_role_list(5, optional_roles=[RoleType.MORDRED])
    validate_role_selection(5, roles_5)

    roles_7 = build_role_list(7, optional_roles=[RoleType.PERCIVAL, RoleType.MORGANA])
    validate_role_selection(7, roles_7)

    roles_10 = build_role_list(
        10,
        optional_roles=[RoleType.PERCIVAL, RoleType.MORGANA, RoleType.MORDRED, RoleType.OBERON],
    )
    validate_role_selection(10, roles_10)


def test_build_role_list_too_many_minion_roles() -> None:
    """Reject when too many minion special roles requested."""
    with pytest.raises(ConfigurationError, match="Too many minion roles"):
        # 5 players needs 2 minions, but we're requesting 3 (Assassin + Morgana + Mordred)
        build_role_list(5, optional_roles=[RoleType.MORGANA, RoleType.MORDRED])


def test_build_role_list_duplicate_role() -> None:
    """Reject duplicate special roles in optional list."""
    with pytest.raises(ConfigurationError, match="specified multiple times"):
        build_role_list(7, optional_roles=[RoleType.MORDRED, RoleType.MORDRED])
