"""Configuration models and validation helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Sequence, Tuple

from .discussion import DiscussionConfig
from .enums import Alignment, RoleType
from .exceptions import ConfigurationError
from .roles import default_roles_for_player_count, role_alignment, validate_role_selection

TEAM_SIZE_TABLE: Dict[int, Tuple[int, int, int, int, int]] = {
    5: (2, 3, 2, 3, 3),
    6: (2, 3, 4, 3, 4),
    7: (2, 3, 3, 4, 4),
    8: (3, 4, 4, 5, 5),
    9: (3, 4, 4, 5, 5),
    10: (3, 4, 4, 5, 5),
}


@dataclass(frozen=True, slots=True)
class MissionConfig:
    """Mission size and fail-threshold configuration for a given player count."""

    player_count: int
    team_sizes: Tuple[int, int, int, int, int]
    required_fail_counts: Tuple[int, int, int, int, int]

    @classmethod
    def for_player_count(cls, player_count: int) -> "MissionConfig":
        if player_count not in TEAM_SIZE_TABLE:
            raise ConfigurationError(f"Unsupported player count: {player_count}")
        fail_threshold = 2 if player_count >= 7 else 1
        fail_counts = (1, 1, 1, fail_threshold, 1)
        return cls(
            player_count=player_count,
            team_sizes=TEAM_SIZE_TABLE[player_count],
            required_fail_counts=fail_counts,
        )


@dataclass(frozen=True, slots=True)
class GameConfig:
    """Immutable game configuration validated against official rules."""

    player_count: int
    roles: Tuple[RoleType, ...]
    lady_of_the_lake_enabled: bool = False
    random_seed: Optional[int] = None
    discussion_config: DiscussionConfig = field(default_factory=DiscussionConfig)
    _mission_config: MissionConfig = field(init=False, repr=False)

    def __post_init__(self) -> None:
        validate_role_selection(self.player_count, self.roles)
        mission_config = MissionConfig.for_player_count(self.player_count)
        object.__setattr__(self, "_mission_config", mission_config)

    @property
    def mission_config(self) -> MissionConfig:
        """Mission sizing parameters for this game configuration."""

        return self._mission_config

    @property
    def alignment_counts(self) -> Tuple[int, int]:
        """Return a tuple of (resistance_count, minion_count)."""

        counts = self.role_alignment_counts()
        return (counts[Alignment.RESISTANCE], counts[Alignment.MINION])

    def role_alignment_counts(self) -> Dict[Alignment, int]:
        """Compute the alignment distribution for the configured roles."""

        counts = {Alignment.RESISTANCE: 0, Alignment.MINION: 0}
        for role in self.roles:
            counts[role_alignment(role)] += 1
        return counts

    def with_roles(self, roles: Sequence[RoleType]) -> "GameConfig":
        """Return a new ``GameConfig`` with the provided role selection."""

        return GameConfig(
            player_count=self.player_count,
            roles=tuple(roles),
            lady_of_the_lake_enabled=self.lady_of_the_lake_enabled,
            random_seed=self.random_seed,
            discussion_config=self.discussion_config,
        )

    @classmethod
    def default(
        cls,
        player_count: int,
        *,
        lady_of_the_lake_enabled: bool = False,
        random_seed: Optional[int] = None,
    ) -> "GameConfig":
        """Instantiate the official default configuration for the given player count."""

        roles = default_roles_for_player_count(player_count)
        return cls(
            player_count=player_count,
            roles=roles,
            lady_of_the_lake_enabled=lady_of_the_lake_enabled,
            random_seed=random_seed,
        )
