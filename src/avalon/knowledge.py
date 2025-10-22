"""Knowledge resolution utilities for Avalon roles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Sequence, Tuple

from .enums import Alignment
from .players import Player, PlayerId
from .roles import ROLE_DEFINITIONS, RoleTag


@dataclass(frozen=True, slots=True)
class KnowledgePacket:
    """Information revealed to a player during the setup phase."""

    visible_player_ids: Tuple[PlayerId, ...]
    ambiguous_player_id_groups: Tuple[Tuple[PlayerId, ...], ...] = ()

    @property
    def has_information(self) -> bool:
        """Return ``True`` when the packet contains any knowledge."""

        return bool(self.visible_player_ids or self.ambiguous_player_id_groups)


def _sorted_ids(players: Iterable[Player]) -> Tuple[PlayerId, ...]:
    return tuple(
        player.player_id
        for player in sorted(
            players,
            key=lambda p: (p.display_name.casefold(), p.player_id),
        )
    )


def compute_setup_knowledge(players: Sequence[Player]) -> Dict[PlayerId, KnowledgePacket]:
    """Generate setup knowledge packets for each player."""

    player_list = list(players)
    knowledge_map: Dict[PlayerId, KnowledgePacket] = {}

    minion_players = [
        player
        for player in player_list
        if ROLE_DEFINITIONS[player.role].alignment is Alignment.MINION
    ]
    non_oberon_minions = [
        player
        for player in minion_players
        if RoleTag.OBERON not in ROLE_DEFINITIONS[player.role].tags
    ]
    mordred_ids = {
        player.player_id
        for player in player_list
        if RoleTag.MORDRED in ROLE_DEFINITIONS[player.role].tags
    }

    percival_candidates = [
        player
        for player in player_list
        if RoleTag.MERLIN in ROLE_DEFINITIONS[player.role].tags
        or RoleTag.MORGANA in ROLE_DEFINITIONS[player.role].tags
    ]

    for player in player_list:
        definition = ROLE_DEFINITIONS[player.role]
        visible: Tuple[PlayerId, ...] = ()
        ambiguous_groups: Tuple[Tuple[PlayerId, ...], ...] = ()

        if RoleTag.MERLIN in definition.tags:
            visible_players = [
                other
                for other in minion_players
                if other.player_id != player.player_id and other.player_id not in mordred_ids
            ]
            visible = _sorted_ids(visible_players)
        elif definition.alignment is Alignment.MINION and RoleTag.OBERON not in definition.tags:
            visible_players = [
                other for other in non_oberon_minions if other.player_id != player.player_id
            ]
            visible = _sorted_ids(visible_players)

        if RoleTag.PERCIVAL in definition.tags and percival_candidates:
            group = _sorted_ids(
                candidate
                for candidate in percival_candidates
                if candidate.player_id != player.player_id
            )
            if group:
                ambiguous_groups = (group,)

        knowledge_map[player.player_id] = KnowledgePacket(
            visible_player_ids=visible,
            ambiguous_player_id_groups=ambiguous_groups,
        )

    return knowledge_map
