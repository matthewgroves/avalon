"""Tests for discussion system data models and logic."""

from __future__ import annotations

import pytest

from avalon.discussion import (
    DiscussionConfig,
    DiscussionPhase,
    DiscussionRound,
    DiscussionStatement,
)


def test_discussion_statement_creation() -> None:
    """Test creating a discussion statement."""
    stmt = DiscussionStatement(
        speaker_id="player1",
        message="I think player3 is suspicious based on the failed mission.",
        round_number=1,
        attempt_number=1,
        phase=DiscussionPhase.POST_MISSION_RESULT,
    )
    assert stmt.speaker_id == "player1"
    assert "suspicious" in stmt.message
    assert stmt.round_number == 1
    assert stmt.phase == DiscussionPhase.POST_MISSION_RESULT


def test_discussion_statement_immutable() -> None:
    """Test that discussion statements are immutable."""
    stmt = DiscussionStatement(
        speaker_id="player1",
        message="Test message",
        round_number=1,
        attempt_number=1,
        phase=DiscussionPhase.PRE_PROPOSAL,
    )
    with pytest.raises(AttributeError):
        stmt.message = "Different message"  # type: ignore


def test_discussion_config_defaults() -> None:
    """Test discussion config default values."""
    config = DiscussionConfig()
    assert config.enabled is True
    assert config.pre_proposal_enabled is True
    assert config.pre_vote_enabled is True
    assert config.post_mission_enabled is True
    assert config.pre_assassination_enabled is True
    assert config.max_statements_per_phase == 1
    assert config.allow_pass is True


def test_discussion_config_custom() -> None:
    """Test custom discussion configuration."""
    config = DiscussionConfig(
        enabled=True,
        pre_proposal_enabled=False,
        pre_vote_enabled=True,
        post_mission_enabled=False,
        pre_assassination_enabled=True,
        max_statements_per_phase=1,
        allow_pass=False,
    )
    assert config.enabled is True
    assert config.pre_proposal_enabled is False
    assert config.pre_vote_enabled is True
    assert config.max_statements_per_phase == 1
    assert config.allow_pass is False


def test_discussion_config_disabled() -> None:
    """Test discussion config with discussions disabled."""
    config = DiscussionConfig(enabled=False)
    assert config.enabled is False
    # Other settings still accessible but wouldn't be used
    assert config.pre_proposal_enabled is True  # Default value


def test_discussion_round_creation() -> None:
    """Test creating a discussion round."""
    round_discussion = DiscussionRound(
        round_number=2,
        attempt_number=1,
        phase=DiscussionPhase.PRE_VOTE,
    )
    assert round_discussion.round_number == 2
    assert round_discussion.attempt_number == 1
    assert round_discussion.phase == DiscussionPhase.PRE_VOTE
    assert len(round_discussion.statements) == 0
    assert len(round_discussion.participants) == 0


def test_discussion_round_add_statement() -> None:
    """Test adding statements to a discussion round."""
    round_discussion = DiscussionRound(
        round_number=1,
        attempt_number=1,
        phase=DiscussionPhase.PRE_PROPOSAL,
    )

    stmt1 = DiscussionStatement(
        speaker_id="player1",
        message="I think we should include player2 on the team.",
        round_number=1,
        attempt_number=1,
        phase=DiscussionPhase.PRE_PROPOSAL,
    )
    round_discussion.add_statement(stmt1)

    assert len(round_discussion.statements) == 1
    assert round_discussion.statements[0] == stmt1
    assert "player1" in round_discussion.participants


def test_discussion_round_multiple_statements() -> None:
    """Test adding multiple statements from different players."""
    round_discussion = DiscussionRound(
        round_number=1,
        attempt_number=2,
        phase=DiscussionPhase.POST_MISSION_RESULT,
    )

    stmt1 = DiscussionStatement(
        speaker_id="player1",
        message="That mission failed suspiciously.",
        round_number=1,
        attempt_number=2,
        phase=DiscussionPhase.POST_MISSION_RESULT,
    )
    stmt2 = DiscussionStatement(
        speaker_id="player2",
        message="I played success! Someone on the team is evil.",
        round_number=1,
        attempt_number=2,
        phase=DiscussionPhase.POST_MISSION_RESULT,
    )
    stmt3 = DiscussionStatement(
        speaker_id="player1",
        message="Player3 was on the last failed mission too.",
        round_number=1,
        attempt_number=2,
        phase=DiscussionPhase.POST_MISSION_RESULT,
    )

    round_discussion.add_statement(stmt1)
    round_discussion.add_statement(stmt2)
    round_discussion.add_statement(stmt3)

    assert len(round_discussion.statements) == 3
    assert len(round_discussion.participants) == 2  # player1 and player2
    assert "player1" in round_discussion.participants
    assert "player2" in round_discussion.participants


def test_discussion_round_get_statements_by_player() -> None:
    """Test retrieving statements by a specific player."""
    round_discussion = DiscussionRound(
        round_number=1,
        attempt_number=1,
        phase=DiscussionPhase.PRE_VOTE,
    )

    stmt1 = DiscussionStatement(
        speaker_id="player1",
        message="First statement",
        round_number=1,
        attempt_number=1,
        phase=DiscussionPhase.PRE_VOTE,
    )
    stmt2 = DiscussionStatement(
        speaker_id="player2",
        message="Second statement",
        round_number=1,
        attempt_number=1,
        phase=DiscussionPhase.PRE_VOTE,
    )
    stmt3 = DiscussionStatement(
        speaker_id="player1",
        message="Third statement",
        round_number=1,
        attempt_number=1,
        phase=DiscussionPhase.PRE_VOTE,
    )

    round_discussion.add_statement(stmt1)
    round_discussion.add_statement(stmt2)
    round_discussion.add_statement(stmt3)

    player1_stmts = round_discussion.get_statements_by_player("player1")
    assert len(player1_stmts) == 2
    assert player1_stmts[0].message == "First statement"
    assert player1_stmts[1].message == "Third statement"

    player2_stmts = round_discussion.get_statements_by_player("player2")
    assert len(player2_stmts) == 1
    assert player2_stmts[0].message == "Second statement"

    player3_stmts = round_discussion.get_statements_by_player("player3")
    assert len(player3_stmts) == 0


def test_discussion_round_has_spoken() -> None:
    """Test checking if a player has spoken in the round."""
    round_discussion = DiscussionRound(
        round_number=1,
        attempt_number=1,
        phase=DiscussionPhase.PRE_PROPOSAL,
    )

    assert not round_discussion.has_spoken("player1")
    assert not round_discussion.has_spoken("player2")

    stmt = DiscussionStatement(
        speaker_id="player1",
        message="Test message",
        round_number=1,
        attempt_number=1,
        phase=DiscussionPhase.PRE_PROPOSAL,
    )
    round_discussion.add_statement(stmt)

    assert round_discussion.has_spoken("player1")
    assert not round_discussion.has_spoken("player2")


def test_discussion_round_to_tuple() -> None:
    """Test converting discussion round to immutable tuple."""
    round_discussion = DiscussionRound(
        round_number=1,
        attempt_number=1,
        phase=DiscussionPhase.PRE_VOTE,
    )

    stmt1 = DiscussionStatement(
        speaker_id="player1",
        message="First",
        round_number=1,
        attempt_number=1,
        phase=DiscussionPhase.PRE_VOTE,
    )
    stmt2 = DiscussionStatement(
        speaker_id="player2",
        message="Second",
        round_number=1,
        attempt_number=1,
        phase=DiscussionPhase.PRE_VOTE,
    )

    round_discussion.add_statement(stmt1)
    round_discussion.add_statement(stmt2)

    statements_tuple = round_discussion.to_tuple()
    assert isinstance(statements_tuple, tuple)
    assert len(statements_tuple) == 2
    assert statements_tuple[0] == stmt1
    assert statements_tuple[1] == stmt2


def test_discussion_phases() -> None:
    """Test all discussion phase enum values."""
    assert DiscussionPhase.PRE_PROPOSAL.value == "pre_proposal"
    assert DiscussionPhase.PRE_VOTE.value == "pre_vote"
    assert DiscussionPhase.POST_MISSION_RESULT.value == "post_mission_result"
    assert DiscussionPhase.PRE_ASSASSINATION.value == "pre_assassination"

    # Ensure all phases are accessible
    phases = [
        DiscussionPhase.PRE_PROPOSAL,
        DiscussionPhase.PRE_VOTE,
        DiscussionPhase.POST_MISSION_RESULT,
        DiscussionPhase.PRE_ASSASSINATION,
    ]
    assert len(phases) == 4
