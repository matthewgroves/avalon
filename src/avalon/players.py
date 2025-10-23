"""Player-related domain models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional, Protocol

from .enums import Alignment, PlayerType, RoleType
from .roles import ROLE_DEFINITIONS, RoleDefinition, role_alignment

PlayerId = str


class AgentHook(Protocol):
    """Placeholder protocol for future agent integrations."""

    def handle_event(self, event: Mapping[str, object], /) -> None:
        """Receive structured event payloads from the game engine."""


@dataclass(frozen=True, slots=True)
class Player:
    """Immutable representation of a game participant."""

    player_id: PlayerId
    display_name: str
    role: RoleType
    player_type: PlayerType = PlayerType.HUMAN
    agent_hook: Optional[AgentHook] = None
    public_history_ids: tuple[str, ...] = ()
    private_note_keys: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.display_name:
            raise ValueError("display_name may not be empty")

    @property
    def alignment(self) -> Alignment:
        """Return the player's team alignment."""

        return role_alignment(self.role)

    @property
    def role_definition(self) -> RoleDefinition:
        """Convenience accessor for role metadata."""

        return ROLE_DEFINITIONS[self.role]

    @property
    def is_agent(self) -> bool:
        """Return True if this player is controlled by an LLM agent."""

        return self.player_type is PlayerType.AGENT

    @property
    def is_human(self) -> bool:
        """Return True if this player is controlled by a human."""

        return self.player_type is PlayerType.HUMAN
