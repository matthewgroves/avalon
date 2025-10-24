"""Discussion and communication system for Avalon games."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Tuple

from .players import PlayerId


class DiscussionPhase(str, Enum):
    """When discussion opportunities occur during gameplay."""

    PRE_PROPOSAL = "pre_proposal"  # Before leader proposes team
    PRE_VOTE = "pre_vote"  # After proposal, before voting
    POST_MISSION_RESULT = "post_mission_result"  # After mission outcome revealed
    PRE_ASSASSINATION = "pre_assassination"  # Before assassin makes guess


@dataclass(frozen=True, slots=True)
class DiscussionStatement:
    """A single statement made by a player during discussion.

    All discussion statements are public knowledge - visible to all players
    and available for agents to use in decision-making.
    """

    speaker_id: PlayerId
    message: str
    round_number: int
    attempt_number: int
    phase: DiscussionPhase
    # Timestamp could be added if needed for ordering


@dataclass(frozen=True, slots=True)
class DiscussionConfig:
    """Configuration for discussion phases in the game.

    Controls when discussions occur and how many statements each player can make.
    """

    enabled: bool = True
    # Which phases have discussion opportunities
    pre_proposal_enabled: bool = True
    pre_vote_enabled: bool = True
    post_mission_enabled: bool = True
    pre_assassination_enabled: bool = True
    # Maximum statements per player per discussion phase (None = unlimited)
    max_statements_per_phase: int | None = 2
    # Allow players to pass/skip their turn
    allow_pass: bool = True


@dataclass
class DiscussionRound:
    """A complete discussion round within a specific phase.

    Tracks all statements made during one discussion opportunity.
    """

    round_number: int
    attempt_number: int
    phase: DiscussionPhase
    statements: list[DiscussionStatement] = field(default_factory=list)
    # Track which players have spoken (for turn management)
    participants: set[PlayerId] = field(default_factory=set)

    def add_statement(self, statement: DiscussionStatement) -> None:
        """Add a statement to this discussion round."""
        self.statements.append(statement)
        self.participants.add(statement.speaker_id)

    def get_statements_by_player(self, player_id: PlayerId) -> list[DiscussionStatement]:
        """Get all statements made by a specific player in this round."""
        return [s for s in self.statements if s.speaker_id == player_id]

    def has_spoken(self, player_id: PlayerId) -> bool:
        """Check if a player has made any statements in this round."""
        return player_id in self.participants

    def to_tuple(self) -> Tuple[DiscussionStatement, ...]:
        """Return statements as immutable tuple."""
        return tuple(self.statements)
