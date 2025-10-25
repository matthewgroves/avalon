"""Agent player interfaces and observation state for LLM-driven decision making."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, Tuple

from .discussion import DiscussionStatement
from .enums import Alignment
from .game_state import GamePhase, MissionSummary, VoteRecord
from .knowledge import KnowledgePacket
from .players import PlayerId
from .roles import RoleType

if TYPE_CHECKING:
    from .game_state import GameState


@dataclass(frozen=True, slots=True)
class AgentObservation:
    """Filtered game state visible to a specific agent player.

    This represents all information an agent can see at a given moment,
    including their role knowledge, public game history, and current phase context.
    """

    # Player identity
    player_id: PlayerId
    display_name: str
    role: RoleType
    alignment: Alignment

    # Role-based knowledge from setup
    knowledge: KnowledgePacket

    # All players in the game
    all_player_ids: Tuple[PlayerId, ...]
    all_player_names: Tuple[str, ...]  # Parallel to all_player_ids

    # Current game state
    phase: GamePhase
    round_number: int
    attempt_number: int
    resistance_score: int
    minion_score: int
    consecutive_rejections: int

    # Leadership
    current_leader_id: PlayerId

    # Team proposal (if in TEAM_VOTE or MISSION phase)
    current_team: Tuple[PlayerId, ...] | None

    # Historical data
    vote_history: Tuple[VoteRecord, ...]
    mission_history: Tuple[MissionSummary, ...]

    # Mission requirements for current round
    required_team_size: int
    required_fail_count: int

    # Public reasoning from other players' decisions
    # Format: List of (player_id, decision_type, public_reasoning) tuples
    public_statements: Tuple[Tuple[PlayerId, str, str], ...] = ()

    # Discussion statements from all players (public knowledge)
    discussion_statements: Tuple[DiscussionStatement, ...] = ()
    # Your private mission actions: list of (round_number, attempt_number, you_played_success)
    # This lets agents reason about missions they personally participated in.
    my_mission_actions: Tuple[Tuple[int, int, bool], ...] = ()


@dataclass(frozen=True, slots=True)
class TeamProposal:
    """Agent's team proposal response."""

    team: Tuple[PlayerId, ...]
    true_reasoning: str = ""
    public_reasoning: str = ""


@dataclass(frozen=True, slots=True)
class VoteDecision:
    """Agent's vote on a proposed team."""

    approve: bool
    true_reasoning: str = ""
    public_reasoning: str = ""


@dataclass(frozen=True, slots=True)
class MissionAction:
    """Agent's mission card submission."""

    success: bool  # True for success, False for fail
    true_reasoning: str = ""
    public_reasoning: str = ""


@dataclass(frozen=True, slots=True)
class AssassinationGuess:
    """Agent's assassination target guess."""

    target_id: PlayerId
    true_reasoning: str = ""
    public_reasoning: str = ""


@dataclass(frozen=True, slots=True)
class DiscussionResponse:
    """Agent's discussion statement response."""

    message: str  # The public statement to make
    true_reasoning: str = ""  # Private reasoning for making this statement


class AgentDecisionMaker(Protocol):
    """Protocol for agent players that make game decisions.

    Implementors receive observation state and return structured decisions.
    All methods should handle errors gracefully and return valid responses.
    """

    def propose_team(self, observation: AgentObservation) -> TeamProposal:
        """Propose a team for the current mission.

        Args:
            observation: Current game state visible to this agent.

        Returns:
            TeamProposal with selected player IDs and optional reasoning.
        """
        ...

    def vote_on_team(self, observation: AgentObservation) -> VoteDecision:
        """Vote to approve or reject the proposed team.

        Args:
            observation: Current game state including the proposed team.

        Returns:
            VoteDecision with approval/rejection and optional reasoning.
        """
        ...

    def execute_mission(self, observation: AgentObservation) -> MissionAction:
        """Submit a mission card (success or fail).

        Args:
            observation: Current game state. Agent must be on current team.

        Returns:
            MissionAction with card choice and optional reasoning.
        """
        ...

    def guess_merlin(self, observation: AgentObservation) -> AssassinationGuess:
        """Guess which player is Merlin (assassin only).

        Args:
            observation: Final game state after resistance wins 3 missions.

        Returns:
            AssassinationGuess with target player ID and optional reasoning.
        """
        ...

    def make_statement(self, observation: AgentObservation, phase: str) -> DiscussionResponse:
        """Generate a discussion statement during a discussion phase.

        Args:
            observation: Current game state including discussion history.
            phase: The discussion phase (PRE_PROPOSAL, PRE_VOTE, etc.)

        Returns:
            DiscussionResponse with the statement message and optional reasoning.
        """
        ...


def build_observation(
    game_state: GameState,
    player_id: PlayerId,
    knowledge: KnowledgePacket,
    public_statements: Tuple[Tuple[PlayerId, str, str], ...] = (),
) -> AgentObservation:
    """Construct an agent observation from game state.

    Args:
        game_state: Current GameState instance.
        player_id: ID of the agent player.
        knowledge: Role-based knowledge from setup.
        public_statements: Tuple of (player_id, decision_type, public_reasoning) from other players.

    Returns:
        AgentObservation with filtered game context.
    """
    from .game_state import GameState as GS

    if not isinstance(game_state, GS):
        raise TypeError("game_state must be a GameState instance")

    player = game_state.players_by_id[player_id]
    from .roles import ROLE_DEFINITIONS

    role_def = ROLE_DEFINITIONS[player.role]

    # Extract player lists
    all_ids = tuple(p.player_id for p in game_state.players)
    all_names = tuple(p.display_name for p in game_state.players)

    # Get mission requirements
    mission_config = game_state.config.mission_config
    required_team_size = mission_config.team_sizes[game_state.round_number - 1]
    required_fail_count = mission_config.required_fail_counts[game_state.round_number - 1]

    # Build observation
    return AgentObservation(
        player_id=player_id,
        display_name=player.display_name,
        role=player.role,
        alignment=role_def.alignment,
        knowledge=knowledge,
        all_player_ids=all_ids,
        all_player_names=all_names,
        phase=game_state.phase,
        round_number=game_state.round_number,
        attempt_number=game_state.attempt_number,
        resistance_score=game_state.resistance_score,
        minion_score=game_state.minion_score,
        consecutive_rejections=game_state.consecutive_rejections,
        current_leader_id=game_state.current_leader.player_id,
        current_team=game_state.current_team,
        vote_history=tuple(game_state.vote_history),
        mission_history=tuple(record.to_public_summary() for record in game_state.mission_history),
        required_team_size=required_team_size,
        required_fail_count=required_fail_count,
        public_statements=public_statements,
        discussion_statements=game_state.all_discussion_statements,
        # Build list of this player's private mission actions
        my_mission_actions=tuple(
            (
                record.round_number,
                record.attempt_number,
                any(
                    a.player_id == player_id and a.decision.name == "SUCCESS"
                    for a in record.actions
                ),
            )
            for record in game_state.mission_history
        ),
    )


__all__ = [
    "AgentDecisionMaker",
    "AgentObservation",
    "AssassinationGuess",
    "DiscussionResponse",
    "MissionAction",
    "TeamProposal",
    "VoteDecision",
    "build_observation",
]
