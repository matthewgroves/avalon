"""Game setup orchestration utilities."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

from .config import GameConfig
from .exceptions import ConfigurationError
from .knowledge import KnowledgePacket, compute_setup_knowledge
from .players import Player, PlayerId


@dataclass(frozen=True, slots=True)
class PlayerRegistration:
    """Registration payload describing an incoming player."""

    display_name: str
    player_id: Optional[str] = None


@dataclass(frozen=True, slots=True)
class PlayerBriefing:
    """Private setup information for a player."""

    player: Player
    knowledge: KnowledgePacket


@dataclass(frozen=True, slots=True)
class SetupResult:
    """Outcome of the game setup process."""

    config: GameConfig
    players: Tuple[Player, ...]
    briefings: Tuple[PlayerBriefing, ...]
    seed: Optional[int]

    @property
    def public_lobby(self) -> Tuple[str, ...]:
        """Return ordered display names for public consumption."""

        return tuple(player.display_name for player in self.players)

    @property
    def knowledge_by_player(self) -> dict[PlayerId, KnowledgePacket]:
        """Return a mapping from player id to knowledge packet."""

        return {briefing.player.player_id: briefing.knowledge for briefing in self.briefings}

    def knowledge_for(self, player_id: str) -> KnowledgePacket:
        """Retrieve the knowledge packet associated with ``player_id``."""

        for briefing in self.briefings:
            if briefing.player.player_id == player_id:
                return briefing.knowledge
        raise KeyError(f"Unknown player id: {player_id}")


def perform_setup(
    config: GameConfig,
    registrations: Sequence[PlayerRegistration],
    *,
    seed: Optional[int] = None,
) -> SetupResult:
    """Perform official Avalon setup using the provided configuration and registrations."""

    _validate_registration_count(config, registrations)
    normalized = _normalize_registrations(registrations)
    assigned_seed = seed if seed is not None else config.random_seed
    rng = random.Random(assigned_seed)
    roles = list(config.roles)
    rng.shuffle(roles)

    assigned_ids: set[str] = {
        registration.player_id for registration in normalized if registration.player_id
    }
    player_records = []
    for index, registration in enumerate(normalized):
        player_id = registration.player_id
        if player_id is None:
            player_id = _generate_player_id(index, assigned_ids)
        assigned_ids.add(player_id)
        player_records.append(
            Player(
                player_id=player_id,
                display_name=registration.display_name,
                role=roles[index],
            )
        )

    players = tuple(player_records)

    knowledge_map = compute_setup_knowledge(players)
    briefings = tuple(
        PlayerBriefing(player=player, knowledge=knowledge_map[player.player_id])
        for player in players
    )

    return SetupResult(
        config=config,
        players=players,
        briefings=briefings,
        seed=assigned_seed,
    )


def _validate_registration_count(
    config: GameConfig, registrations: Sequence[PlayerRegistration]
) -> None:
    if len(registrations) != config.player_count:
        raise ConfigurationError(
            "Player registration count does not match configuration: "
            f"expected {config.player_count}, received {len(registrations)}"
        )


def _normalize_registrations(
    registrations: Sequence[PlayerRegistration],
) -> Tuple[PlayerRegistration, ...]:
    seen_names: set[str] = set()
    seen_ids: set[str] = set()
    normalized: list[PlayerRegistration] = []

    for registration in registrations:
        display_name = registration.display_name.strip()
        if not display_name:
            raise ConfigurationError("Player display names must be non-empty")

        lowered = display_name.casefold()
        if lowered in seen_names:
            raise ConfigurationError("Duplicate player name detected: " f"{display_name}")
        seen_names.add(lowered)

        player_id = registration.player_id
        if player_id is not None:
            cleaned_id = player_id.strip()
            if not cleaned_id:
                raise ConfigurationError("Player identifiers must be non-empty when provided")
            if cleaned_id in seen_ids:
                raise ConfigurationError("Duplicate player identifier detected: " f"{cleaned_id}")
            seen_ids.add(cleaned_id)
            normalized.append(PlayerRegistration(display_name=display_name, player_id=cleaned_id))
        else:
            normalized.append(PlayerRegistration(display_name=display_name))

    return tuple(normalized)


def _generate_player_id(index: int, existing_ids: set[str]) -> str:
    base = f"player_{index + 1}"
    candidate = base
    suffix = 1
    while candidate in existing_ids:
        suffix += 1
        candidate = f"{base}_{suffix}"
    return candidate
