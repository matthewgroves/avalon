"""Agent manager for coordinating LLM clients with agent players."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from .agents import (
    AgentObservation,
    AssassinationGuess,
    MissionAction,
    TeamProposal,
    VoteDecision,
    build_observation,
)
from .game_state import GameState
from .players import PlayerId

if TYPE_CHECKING:
    from .setup import PlayerBriefing, SetupResult


class LLMClient(Protocol):
    """Protocol for LLM clients."""

    def propose_team(self, observation: AgentObservation) -> TeamProposal: ...
    def vote_on_team(self, observation: AgentObservation) -> VoteDecision: ...
    def execute_mission(self, observation: AgentObservation) -> MissionAction: ...
    def guess_merlin(self, observation: AgentObservation) -> AssassinationGuess: ...


@dataclass
class AgentManager:
    """Manages agent players and their LLM clients.

    Coordinates building observations, calling LLM clients, and tracking
    agent briefings for knowledge extraction.
    """

    briefings_by_player_id: dict[PlayerId, PlayerBriefing]
    client: LLMClient
    public_statements: list[tuple[PlayerId, str, str]] | None = None

    @classmethod
    def from_setup(cls, setup_result: SetupResult, client: LLMClient) -> AgentManager:
        """Create an agent manager from setup result.

        Args:
            setup_result: SetupResult containing player briefings.
            client: LLM client to use for all agent decisions.

        Returns:
            AgentManager configured with briefings and client.
        """
        briefings_map = {briefing.player.player_id: briefing for briefing in setup_result.briefings}
        return cls(briefings_by_player_id=briefings_map, client=client)

    def set_public_statements(self, statements: list[tuple[PlayerId, str, str]]) -> None:
        """Update the public statements list reference."""
        self.public_statements = statements

    def is_agent(self, player_id: PlayerId, state: GameState) -> bool:
        """Check if a player is an agent."""
        player = state.players_by_id.get(player_id)
        return player is not None and player.is_agent

    def propose_team(self, player_id: PlayerId, state: GameState) -> TeamProposal:
        """Get team proposal from agent.

        Args:
            player_id: ID of the agent leader.
            state: Current game state.

        Returns:
            TeamProposal from the LLM client.
        """
        observation = self._build_observation(player_id, state)
        return self.client.propose_team(observation)

    def vote_on_team(self, player_id: PlayerId, state: GameState) -> VoteDecision:
        """Get vote decision from agent.

        Args:
            player_id: ID of the agent voter.
            state: Current game state.

        Returns:
            VoteDecision from the LLM client.
        """
        observation = self._build_observation(player_id, state)
        return self.client.vote_on_team(observation)

    def execute_mission(self, player_id: PlayerId, state: GameState) -> MissionAction:
        """Get mission action from agent.

        Args:
            player_id: ID of the agent on the mission team.
            state: Current game state.

        Returns:
            MissionAction from the LLM client.
        """
        observation = self._build_observation(player_id, state)
        return self.client.execute_mission(observation)

    def guess_merlin(self, player_id: PlayerId, state: GameState) -> AssassinationGuess:
        """Get Merlin guess from agent assassin.

        Args:
            player_id: ID of the agent assassin.
            state: Current game state.

        Returns:
            AssassinationGuess from the LLM client.
        """
        observation = self._build_observation(player_id, state)
        return self.client.guess_merlin(observation)

    def _build_observation(self, player_id: PlayerId, state: GameState) -> AgentObservation:
        """Build an observation for an agent player."""
        briefing = self.briefings_by_player_id[player_id]
        # Pass public statements if available
        statements_tuple = tuple(self.public_statements) if self.public_statements else ()
        return build_observation(state, player_id, briefing.knowledge, statements_tuple)


__all__ = ["AgentManager", "LLMClient"]
