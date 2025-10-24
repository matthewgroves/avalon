"""Tests for discussion functionality in GameState."""

from __future__ import annotations

import pytest

from avalon.config import GameConfig
from avalon.discussion import DiscussionPhase, DiscussionStatement
from avalon.exceptions import InvalidActionError
from avalon.game_state import GameState
from avalon.setup import PlayerRegistration, perform_setup


@pytest.fixture
def game_state() -> GameState:
    """Create a basic game state for testing."""
    config = GameConfig.default(5)
    registrations = [PlayerRegistration(f"Player {i}") for i in range(1, 6)]
    setup = perform_setup(config, registrations, seed=42)
    return GameState.from_setup(setup)


def test_game_state_has_discussion_tracking(game_state: GameState) -> None:
    """Test that GameState has discussion tracking fields."""
    assert hasattr(game_state, "discussion_history")
    assert hasattr(game_state, "current_discussion")
    assert len(game_state.discussion_history) == 0
    assert game_state.current_discussion is None


def test_start_discussion(game_state: GameState) -> None:
    """Test starting a discussion round."""
    game_state.start_discussion(DiscussionPhase.PRE_PROPOSAL)

    assert game_state.current_discussion is not None
    assert game_state.current_discussion.round_number == 1
    assert game_state.current_discussion.attempt_number == 1
    assert game_state.current_discussion.phase == DiscussionPhase.PRE_PROPOSAL
    assert len(game_state.current_discussion.statements) == 0


def test_start_discussion_when_already_in_progress(game_state: GameState) -> None:
    """Test that starting a discussion when one is already in progress raises an error."""
    game_state.start_discussion(DiscussionPhase.PRE_PROPOSAL)

    with pytest.raises(InvalidActionError, match="discussion is already in progress"):
        game_state.start_discussion(DiscussionPhase.PRE_VOTE)


def test_add_discussion_statement(game_state: GameState) -> None:
    """Test adding a statement to a discussion."""
    game_state.start_discussion(DiscussionPhase.PRE_PROPOSAL)

    player_id = game_state.players[0].player_id
    statement = DiscussionStatement(
        speaker_id=player_id,
        message="I think we should include player2 on the team.",
        round_number=1,
        attempt_number=1,
        phase=DiscussionPhase.PRE_PROPOSAL,
    )

    game_state.add_discussion_statement(statement)

    assert len(game_state.current_discussion.statements) == 1  # type: ignore
    assert game_state.current_discussion.statements[0] == statement  # type: ignore


def test_add_statement_without_discussion(game_state: GameState) -> None:
    """Test that adding a statement without a discussion in progress raises an error."""
    player_id = game_state.players[0].player_id
    statement = DiscussionStatement(
        speaker_id=player_id,
        message="Test message",
        round_number=1,
        attempt_number=1,
        phase=DiscussionPhase.PRE_PROPOSAL,
    )

    with pytest.raises(InvalidActionError, match="No discussion in progress"):
        game_state.add_discussion_statement(statement)


def test_add_statement_wrong_round(game_state: GameState) -> None:
    """Test that adding a statement with wrong round number raises an error."""
    game_state.start_discussion(DiscussionPhase.PRE_PROPOSAL)

    player_id = game_state.players[0].player_id
    statement = DiscussionStatement(
        speaker_id=player_id,
        message="Test message",
        round_number=2,  # Wrong round
        attempt_number=1,
        phase=DiscussionPhase.PRE_PROPOSAL,
    )

    with pytest.raises(InvalidActionError, match="round.*doesn't match"):
        game_state.add_discussion_statement(statement)


def test_add_statement_wrong_attempt(game_state: GameState) -> None:
    """Test that adding a statement with wrong attempt number raises an error."""
    game_state.start_discussion(DiscussionPhase.PRE_PROPOSAL)

    player_id = game_state.players[0].player_id
    statement = DiscussionStatement(
        speaker_id=player_id,
        message="Test message",
        round_number=1,
        attempt_number=2,  # Wrong attempt
        phase=DiscussionPhase.PRE_PROPOSAL,
    )

    with pytest.raises(InvalidActionError, match="attempt.*doesn't match"):
        game_state.add_discussion_statement(statement)


def test_add_statement_wrong_phase(game_state: GameState) -> None:
    """Test that adding a statement with wrong phase raises an error."""
    game_state.start_discussion(DiscussionPhase.PRE_PROPOSAL)

    player_id = game_state.players[0].player_id
    statement = DiscussionStatement(
        speaker_id=player_id,
        message="Test message",
        round_number=1,
        attempt_number=1,
        phase=DiscussionPhase.PRE_VOTE,  # Wrong phase
    )

    with pytest.raises(InvalidActionError, match="phase.*doesn't match"):
        game_state.add_discussion_statement(statement)


def test_end_discussion(game_state: GameState) -> None:
    """Test ending a discussion round."""
    game_state.start_discussion(DiscussionPhase.PRE_PROPOSAL)

    player_id = game_state.players[0].player_id
    statement = DiscussionStatement(
        speaker_id=player_id,
        message="Test message",
        round_number=1,
        attempt_number=1,
        phase=DiscussionPhase.PRE_PROPOSAL,
    )
    game_state.add_discussion_statement(statement)

    game_state.end_discussion()

    assert game_state.current_discussion is None
    assert len(game_state.discussion_history) == 1
    assert game_state.discussion_history[0].statements[0] == statement


def test_end_discussion_without_active_discussion(game_state: GameState) -> None:
    """Test that ending a discussion when none is active raises an error."""
    with pytest.raises(InvalidActionError, match="No discussion to end"):
        game_state.end_discussion()


def test_multiple_discussion_rounds(game_state: GameState) -> None:
    """Test multiple discussion rounds."""
    # First discussion
    game_state.start_discussion(DiscussionPhase.PRE_PROPOSAL)
    player_id = game_state.players[0].player_id
    stmt1 = DiscussionStatement(
        speaker_id=player_id,
        message="First discussion",
        round_number=1,
        attempt_number=1,
        phase=DiscussionPhase.PRE_PROPOSAL,
    )
    game_state.add_discussion_statement(stmt1)
    game_state.end_discussion()

    # Second discussion
    game_state.start_discussion(DiscussionPhase.PRE_VOTE)
    stmt2 = DiscussionStatement(
        speaker_id=player_id,
        message="Second discussion",
        round_number=1,
        attempt_number=1,
        phase=DiscussionPhase.PRE_VOTE,
    )
    game_state.add_discussion_statement(stmt2)
    game_state.end_discussion()

    assert len(game_state.discussion_history) == 2
    assert game_state.discussion_history[0].phase == DiscussionPhase.PRE_PROPOSAL
    assert game_state.discussion_history[1].phase == DiscussionPhase.PRE_VOTE


def test_discussions_property(game_state: GameState) -> None:
    """Test the discussions property returns immutable tuple."""
    game_state.start_discussion(DiscussionPhase.PRE_PROPOSAL)
    player_id = game_state.players[0].player_id
    stmt = DiscussionStatement(
        speaker_id=player_id,
        message="Test",
        round_number=1,
        attempt_number=1,
        phase=DiscussionPhase.PRE_PROPOSAL,
    )
    game_state.add_discussion_statement(stmt)
    game_state.end_discussion()

    discussions = game_state.discussions
    assert isinstance(discussions, tuple)
    assert len(discussions) == 1
    assert discussions[0].statements[0] == stmt


def test_all_discussion_statements_property(game_state: GameState) -> None:
    """Test getting all discussion statements across all rounds."""
    # First discussion
    game_state.start_discussion(DiscussionPhase.PRE_PROPOSAL)
    player_id = game_state.players[0].player_id
    stmt1 = DiscussionStatement(
        speaker_id=player_id,
        message="First",
        round_number=1,
        attempt_number=1,
        phase=DiscussionPhase.PRE_PROPOSAL,
    )
    game_state.add_discussion_statement(stmt1)
    game_state.end_discussion()

    # Second discussion
    game_state.start_discussion(DiscussionPhase.PRE_VOTE)
    stmt2 = DiscussionStatement(
        speaker_id=player_id,
        message="Second",
        round_number=1,
        attempt_number=1,
        phase=DiscussionPhase.PRE_VOTE,
    )
    game_state.add_discussion_statement(stmt2)

    # Should include both completed and current discussion
    all_statements = game_state.all_discussion_statements
    assert isinstance(all_statements, tuple)
    assert len(all_statements) == 2
    assert stmt1 in all_statements
    assert stmt2 in all_statements


def test_all_discussion_statements_empty(game_state: GameState) -> None:
    """Test all_discussion_statements when there are no discussions."""
    all_statements = game_state.all_discussion_statements
    assert isinstance(all_statements, tuple)
    assert len(all_statements) == 0
