"""Role metadata and validation helpers for Avalon."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from typing import Mapping, Sequence

from .enums import Alignment, RoleType
from .exceptions import ConfigurationError


class RoleTag(str):
    """String markers describing special role traits."""

    MERLIN = "merlin"
    PERCIVAL = "percival"
    ASSASSIN = "assassin"
    MORGANA = "morgana"
    MORDRED = "mordred"
    OBERON = "oberon"
    GENERIC_SERVANT = "generic_servant"
    GENERIC_MINION = "generic_minion"


@dataclass(frozen=True, slots=True)
class RoleDefinition:
    """Canonical metadata for a single Avalon role."""

    role: RoleType
    alignment: Alignment
    tags: frozenset[str]
    assassin_target: bool = False

    def has_tag(self, tag: str) -> bool:
        """Check whether the role definition includes a specific tag."""

        return tag in self.tags


ROLE_DEFINITIONS: Mapping[RoleType, RoleDefinition] = {
    RoleType.MERLIN: RoleDefinition(
        role=RoleType.MERLIN,
        alignment=Alignment.RESISTANCE,
        tags=frozenset({RoleTag.MERLIN}),
        assassin_target=True,
    ),
    RoleType.PERCIVAL: RoleDefinition(
        role=RoleType.PERCIVAL,
        alignment=Alignment.RESISTANCE,
        tags=frozenset({RoleTag.PERCIVAL}),
    ),
    RoleType.LOYAL_SERVANT: RoleDefinition(
        role=RoleType.LOYAL_SERVANT,
        alignment=Alignment.RESISTANCE,
        tags=frozenset({RoleTag.GENERIC_SERVANT}),
    ),
    RoleType.ASSASSIN: RoleDefinition(
        role=RoleType.ASSASSIN,
        alignment=Alignment.MINION,
        tags=frozenset({RoleTag.ASSASSIN}),
    ),
    RoleType.MORGANA: RoleDefinition(
        role=RoleType.MORGANA,
        alignment=Alignment.MINION,
        tags=frozenset({RoleTag.MORGANA}),
    ),
    RoleType.MORDRED: RoleDefinition(
        role=RoleType.MORDRED,
        alignment=Alignment.MINION,
        tags=frozenset({RoleTag.MORDRED}),
    ),
    RoleType.OBERON: RoleDefinition(
        role=RoleType.OBERON,
        alignment=Alignment.MINION,
        tags=frozenset({RoleTag.OBERON}),
    ),
    RoleType.MINION_OF_MORDRED: RoleDefinition(
        role=RoleType.MINION_OF_MORDRED,
        alignment=Alignment.MINION,
        tags=frozenset({RoleTag.GENERIC_MINION}),
    ),
}


EXPECTED_ALIGNMENT_COUNTS: Mapping[int, tuple[int, int]] = {
    5: (3, 2),
    6: (4, 2),
    7: (4, 3),
    8: (5, 3),
    9: (6, 3),
    10: (6, 4),
}


UNIQUE_ROLE_TYPES: frozenset[RoleType] = frozenset(
    {
        RoleType.MERLIN,
        RoleType.PERCIVAL,
        RoleType.ASSASSIN,
        RoleType.MORGANA,
        RoleType.MORDRED,
        RoleType.OBERON,
    }
)


DEFAULT_ROLE_SET_BY_PLAYER_COUNT: Mapping[int, tuple[RoleType, ...]] = {
    5: (
        RoleType.MERLIN,
        RoleType.PERCIVAL,
        RoleType.LOYAL_SERVANT,
        RoleType.ASSASSIN,
        RoleType.MORGANA,
    ),
    6: (
        RoleType.MERLIN,
        RoleType.PERCIVAL,
        RoleType.LOYAL_SERVANT,
        RoleType.LOYAL_SERVANT,
        RoleType.ASSASSIN,
        RoleType.MORGANA,
    ),
    7: (
        RoleType.MERLIN,
        RoleType.PERCIVAL,
        RoleType.LOYAL_SERVANT,
        RoleType.LOYAL_SERVANT,
        RoleType.ASSASSIN,
        RoleType.MORGANA,
        RoleType.MORDRED,
    ),
    8: (
        RoleType.MERLIN,
        RoleType.PERCIVAL,
        RoleType.LOYAL_SERVANT,
        RoleType.LOYAL_SERVANT,
        RoleType.LOYAL_SERVANT,
        RoleType.ASSASSIN,
        RoleType.MORGANA,
        RoleType.MORDRED,
    ),
    9: (
        RoleType.MERLIN,
        RoleType.PERCIVAL,
        RoleType.LOYAL_SERVANT,
        RoleType.LOYAL_SERVANT,
        RoleType.LOYAL_SERVANT,
        RoleType.LOYAL_SERVANT,
        RoleType.ASSASSIN,
        RoleType.MORGANA,
        RoleType.MORDRED,
    ),
    10: (
        RoleType.MERLIN,
        RoleType.PERCIVAL,
        RoleType.LOYAL_SERVANT,
        RoleType.LOYAL_SERVANT,
        RoleType.LOYAL_SERVANT,
        RoleType.LOYAL_SERVANT,
        RoleType.ASSASSIN,
        RoleType.MORGANA,
        RoleType.MORDRED,
        RoleType.OBERON,
    ),
}


def role_alignment(role: RoleType) -> Alignment:
    """Return the alignment for the provided role."""

    return ROLE_DEFINITIONS[role].alignment


def default_roles_for_player_count(player_count: int) -> tuple[RoleType, ...]:
    """Retrieve the official default role set for the supplied player count."""

    if player_count not in DEFAULT_ROLE_SET_BY_PLAYER_COUNT:
        raise ConfigurationError(f"Unsupported player count: {player_count}")
    return DEFAULT_ROLE_SET_BY_PLAYER_COUNT[player_count]


def validate_role_selection(player_count: int, roles: Sequence[RoleType]) -> None:
    """Ensure the provided role selection adheres to official rule constraints."""

    if player_count not in EXPECTED_ALIGNMENT_COUNTS:
        raise ConfigurationError(f"Unsupported player count: {player_count}")

    if len(roles) != player_count:
        raise ConfigurationError(f"Expected {player_count} roles, received {len(roles)}")

    alignment_counter = Counter(role_alignment(role) for role in roles)
    expected_resistance, expected_minions = EXPECTED_ALIGNMENT_COUNTS[player_count]

    if alignment_counter[Alignment.RESISTANCE] != expected_resistance:
        raise ConfigurationError(
            "Resistance role count mismatch: "
            f"expected {expected_resistance}, "
            f"received {alignment_counter[Alignment.RESISTANCE]}"
        )

    if alignment_counter[Alignment.MINION] != expected_minions:
        raise ConfigurationError(
            "Minion role count mismatch: "
            f"expected {expected_minions}, "
            f"received {alignment_counter[Alignment.MINION]}"
        )

    # Enforce uniqueness of special roles.
    for unique_role in UNIQUE_ROLE_TYPES:
        if roles.count(unique_role) > 1:
            raise ConfigurationError(f"Role {unique_role.value} may only appear once")

    role_tags = [ROLE_DEFINITIONS[role].tags for role in roles]
    tags_flat = {tag for tags in role_tags for tag in tags}

    if RoleTag.MERLIN in tags_flat and RoleTag.ASSASSIN not in tags_flat:
        raise ConfigurationError("Merlin requires the Assassin to be present")

    if RoleTag.PERCIVAL in tags_flat and RoleTag.MERLIN not in tags_flat:
        raise ConfigurationError("Percival requires Merlin to be present")


@lru_cache(maxsize=None)
def role_tags(role: RoleType) -> frozenset[str]:
    """Helper returning cached tag frozenset for the given role."""

    return ROLE_DEFINITIONS[role].tags


def is_minion(role: RoleType) -> bool:
    """Determine whether the role is aligned with the minions of Mordred."""

    return role_alignment(role) is Alignment.MINION


def is_resistance(role: RoleType) -> bool:
    """Determine whether the role is aligned with the resistance."""

    return role_alignment(role) is Alignment.RESISTANCE


def build_role_list(
    player_count: int,
    *,
    optional_roles: Sequence[RoleType] | None = None,
) -> tuple[RoleType, ...]:
    """Build a role list from player count and optional special role selections.

    Always includes Merlin and Assassin (essential roles). Fills remaining slots
    with generic LOYAL_SERVANT and MINION_OF_MORDRED to meet alignment requirements.

    Args:
        player_count: Number of players (5-10).
        optional_roles: Optional special roles to include (Percival, Morgana, Mordred, Oberon).

    Returns:
        Tuple of roles matching the player count and alignment requirements.

    Raises:
        ConfigurationError: If player count is invalid or role combination is impossible.
    """
    if player_count not in EXPECTED_ALIGNMENT_COUNTS:
        raise ConfigurationError(f"Unsupported player count: {player_count}")

    expected_resistance, expected_minions = EXPECTED_ALIGNMENT_COUNTS[player_count]

    # Start with essential roles
    roles: list[RoleType] = [RoleType.MERLIN, RoleType.ASSASSIN]
    resistance_count = 1  # Merlin
    minion_count = 1  # Assassin

    # Add optional roles if provided
    if optional_roles:
        for role in optional_roles:
            if role in (RoleType.MERLIN, RoleType.ASSASSIN):
                continue  # Already included
            if role in (RoleType.LOYAL_SERVANT, RoleType.MINION_OF_MORDRED):
                continue  # Generic roles shouldn't be in optional list
            if roles.count(role) > 0:
                raise ConfigurationError(f"Role {role.value} specified multiple times")

            alignment = role_alignment(role)
            if alignment is Alignment.RESISTANCE:
                if resistance_count >= expected_resistance:
                    raise ConfigurationError(
                        f"Too many resistance roles for {player_count} players"
                    )
                resistance_count += 1
            else:
                if minion_count >= expected_minions:
                    raise ConfigurationError(f"Too many minion roles for {player_count} players")
                minion_count += 1

            roles.append(role)

    # Fill remaining slots with generic roles
    while resistance_count < expected_resistance:
        roles.append(RoleType.LOYAL_SERVANT)
        resistance_count += 1

    while minion_count < expected_minions:
        roles.append(RoleType.MINION_OF_MORDRED)
        minion_count += 1

    return tuple(roles)
