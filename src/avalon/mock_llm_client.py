"""Mock LLM client for deterministic testing of agent behaviors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .agents import (
    AgentObservation,
    AssassinationGuess,
    MissionAction,
    TeamProposal,
    VoteDecision,
)


@dataclass
class MockLLMClient:
    """Deterministic LLM client for testing.

    Allows scripting responses for agent decision-making tests.
    """

    team_proposals: list[TeamProposal] | None = None
    vote_decisions: list[VoteDecision] | None = None
    mission_actions: list[MissionAction] | None = None
    assassination_guesses: list[AssassinationGuess] | None = None

    # Strategy functions for more complex test scenarios
    propose_team_fn: Callable[[AgentObservation], TeamProposal] | None = None
    vote_on_team_fn: Callable[[AgentObservation], VoteDecision] | None = None
    execute_mission_fn: Callable[[AgentObservation], MissionAction] | None = None
    guess_merlin_fn: Callable[[AgentObservation], AssassinationGuess] | None = None

    def __post_init__(self) -> None:
        """Initialize response queues."""
        self._team_proposal_index = 0
        self._vote_decision_index = 0
        self._mission_action_index = 0
        self._assassination_guess_index = 0

    def propose_team(self, observation: AgentObservation) -> TeamProposal:
        """Return scripted or generated team proposal."""
        if self.propose_team_fn:
            return self.propose_team_fn(observation)

        if self.team_proposals and self._team_proposal_index < len(self.team_proposals):
            response = self.team_proposals[self._team_proposal_index]
            self._team_proposal_index += 1
            return response

        # Default fallback: select first N players
        team = observation.all_player_ids[: observation.required_team_size]
        return TeamProposal(
            team=team,
            private_reasoning="Mock default proposal",
            public_reasoning="I chose these players",
        )

    def vote_on_team(self, observation: AgentObservation) -> VoteDecision:
        """Return scripted or generated vote decision."""
        if self.vote_on_team_fn:
            return self.vote_on_team_fn(observation)

        if self.vote_decisions and self._vote_decision_index < len(self.vote_decisions):
            response = self.vote_decisions[self._vote_decision_index]
            self._vote_decision_index += 1
            return response

        # Default fallback: always approve
        return VoteDecision(
            approve=True,
            private_reasoning="Mock default approve",
            public_reasoning="This team looks good",
        )

    def execute_mission(self, observation: AgentObservation) -> MissionAction:
        """Return scripted or generated mission action."""
        if self.execute_mission_fn:
            return self.execute_mission_fn(observation)

        if self.mission_actions and self._mission_action_index < len(self.mission_actions):
            response = self.mission_actions[self._mission_action_index]
            self._mission_action_index += 1
            return response

        # Default fallback: always success
        return MissionAction(
            success=True,
            private_reasoning="Mock default success",
            public_reasoning="Playing for the team",
        )

    def guess_merlin(self, observation: AgentObservation) -> AssassinationGuess:
        """Return scripted or generated assassination guess."""
        if self.guess_merlin_fn:
            return self.guess_merlin_fn(observation)

        if self.assassination_guesses and self._assassination_guess_index < len(
            self.assassination_guesses
        ):
            response = self.assassination_guesses[self._assassination_guess_index]
            self._assassination_guess_index += 1
            return response

        # Default fallback: guess first player
        return AssassinationGuess(
            target_id=observation.all_player_ids[0],
            private_reasoning="Mock default guess",
            public_reasoning="They seemed suspicious",
        )


def create_simple_agent_strategy(
    always_approve: bool = True,
    always_succeed: bool = True,
) -> MockLLMClient:
    """Create a mock client with simple, consistent strategies.

    Args:
        always_approve: If True, agent always approves teams.
        always_succeed: If True, agent always plays success cards.

    Returns:
        MockLLMClient configured with the specified strategies.
    """

    def propose_team(obs: AgentObservation) -> TeamProposal:
        # Propose first N players
        team = obs.all_player_ids[: obs.required_team_size]
        return TeamProposal(
            team=team,
            private_reasoning="Simple strategy: first N players",
            public_reasoning="These players seem trustworthy",
        )

    def vote_on_team(obs: AgentObservation) -> VoteDecision:
        action = "approve" if always_approve else "reject"
        return VoteDecision(
            approve=always_approve,
            private_reasoning=f"Always {action}",
            public_reasoning="I think this team will work well"
            if always_approve
            else "I don't trust this team",
        )

    def execute_mission(obs: AgentObservation) -> MissionAction:
        action = "succeed" if always_succeed else "fail"
        return MissionAction(
            success=always_succeed,
            private_reasoning=f"Always {action}",
            public_reasoning="Doing my best for the team",
        )

    def guess_merlin(obs: AgentObservation) -> AssassinationGuess:
        # Guess a random player (first non-self)
        target = next(
            (pid for pid in obs.all_player_ids if pid != obs.player_id), obs.all_player_ids[0]
        )
        return AssassinationGuess(
            target_id=target,
            private_reasoning="Simple guess",
            public_reasoning="They made suspiciously good decisions",
        )

    return MockLLMClient(
        propose_team_fn=propose_team,
        vote_on_team_fn=vote_on_team,
        execute_mission_fn=execute_mission,
        guess_merlin_fn=guess_merlin,
    )


__all__ = ["MockLLMClient", "create_simple_agent_strategy"]
