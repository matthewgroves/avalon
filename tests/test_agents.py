"""Tests for agent interfaces and observation state construction."""

from __future__ import annotations

from avalon.agents import (
    AssassinationGuess,
    MissionAction,
    TeamProposal,
    VoteDecision,
    build_observation,
)
from avalon.config import GameConfig
from avalon.enums import Alignment
from avalon.game_state import GamePhase, GameState
from avalon.roles import RoleType, build_role_list
from avalon.setup import PlayerRegistration, perform_setup


def test_build_observation_basic() -> None:
    """build_observation creates observation with correct player identity."""
    # Setup a 5-player game
    registrations = [
        PlayerRegistration("Alice"),
        PlayerRegistration("Bob"),
        PlayerRegistration("Carol"),
        PlayerRegistration("Dave"),
        PlayerRegistration("Eve"),
    ]
    roles = build_role_list(5)
    config = GameConfig(player_count=5, roles=roles)
    setup = perform_setup(config, registrations)
    state = GameState.from_setup(setup)

    # Build observation for player_1 (Alice)
    player_1_briefing = next(b for b in setup.briefings if b.player.player_id == "player_1")
    observation = build_observation(state, "player_1", player_1_briefing.knowledge)

    # Check player identity
    assert observation.player_id == "player_1"
    assert observation.display_name == "Alice"
    assert observation.role in roles
    assert observation.alignment in (Alignment.RESISTANCE, Alignment.MINION)

    # Check game state
    assert observation.phase == GamePhase.TEAM_PROPOSAL
    assert observation.round_number == 1
    assert observation.attempt_number == 1
    assert observation.resistance_score == 0
    assert observation.minion_score == 0
    assert observation.consecutive_rejections == 0

    # Check player lists
    assert len(observation.all_player_ids) == 5
    assert len(observation.all_player_names) == 5
    assert "player_1" in observation.all_player_ids
    assert "Alice" in observation.all_player_names

    # Check mission requirements
    assert observation.required_team_size == 2  # First mission in 5-player game
    assert observation.required_fail_count == 1


def test_build_observation_includes_knowledge() -> None:
    """build_observation preserves role-based knowledge."""
    registrations = [PlayerRegistration(f"Player{i}") for i in range(5)]
    roles = build_role_list(5)
    config = GameConfig(player_count=5, roles=roles)
    setup = perform_setup(config, registrations)
    state = GameState.from_setup(setup)

    # Find Merlin (who has visible_player_ids knowledge)
    merlin_briefing = next(b for b in setup.briefings if b.player.role == RoleType.MERLIN)
    observation = build_observation(
        state, merlin_briefing.player.player_id, merlin_briefing.knowledge
    )

    # Merlin should have knowledge of minions
    assert observation.knowledge.has_information
    assert len(observation.knowledge.visible_player_ids) > 0


def test_build_observation_tracks_game_progress() -> None:
    """build_observation reflects game state changes."""
    registrations = [PlayerRegistration(f"Player{i}") for i in range(5)]
    roles = build_role_list(5)
    config = GameConfig(player_count=5, roles=roles)
    setup = perform_setup(config, registrations)
    state = GameState.from_setup(setup)

    player_1_briefing = next(b for b in setup.briefings if b.player.player_id == "player_1")

    # Propose and approve a team
    leader = state.current_leader
    state.propose_team(leader.player_id, ("player_1", "player_2"))
    votes = {p.player_id: True for p in state.players}
    state.vote_on_team(votes)

    # Build observation in MISSION phase
    observation = build_observation(state, "player_1", player_1_briefing.knowledge)

    assert observation.phase == GamePhase.MISSION
    assert observation.current_team == ("player_1", "player_2")
    assert len(observation.vote_history) == 1
    assert observation.vote_history[0].approved is True


def test_build_observation_includes_mission_history() -> None:
    """build_observation includes public mission summaries."""
    registrations = [PlayerRegistration(f"Player{i}") for i in range(5)]
    roles = build_role_list(5)
    config = GameConfig(player_count=5, roles=roles)
    setup = perform_setup(config, registrations)
    state = GameState.from_setup(setup)

    player_1_briefing = next(b for b in setup.briefings if b.player.player_id == "player_1")

    # Complete a mission
    leader = state.current_leader
    state.propose_team(leader.player_id, ("player_1", "player_2"))
    votes = {p.player_id: True for p in state.players}
    state.vote_on_team(votes)

    from avalon.game_state import MissionDecision

    decisions = {"player_1": MissionDecision.SUCCESS, "player_2": MissionDecision.SUCCESS}
    state.submit_mission(decisions)

    # Build observation after mission
    observation = build_observation(state, "player_1", player_1_briefing.knowledge)

    assert len(observation.mission_history) == 1
    mission_summary = observation.mission_history[0]
    assert mission_summary.round_number == 1
    assert mission_summary.team == ("player_1", "player_2")
    assert mission_summary.fail_count == 0


def test_team_proposal_structure() -> None:
    """TeamProposal correctly stores team and reasoning."""
    proposal = TeamProposal(
        team=("player_1", "player_2", "player_3"),
        reasoning="Choosing trusted players based on voting patterns",
    )
    assert len(proposal.team) == 3
    assert "player_1" in proposal.team
    assert proposal.reasoning != ""


def test_vote_decision_structure() -> None:
    """VoteDecision correctly stores approval and reasoning."""
    approve = VoteDecision(approve=True, reasoning="Team composition looks good")
    reject = VoteDecision(approve=False, reasoning="Suspicious behavior from player_3")

    assert approve.approve is True
    assert reject.approve is False
    assert approve.reasoning != ""


def test_mission_action_structure() -> None:
    """MissionAction correctly stores card choice and reasoning."""
    success_action = MissionAction(success=True, reasoning="Resistance player")
    fail_action = MissionAction(success=False, reasoning="Sabotaging mission")

    assert success_action.success is True
    assert fail_action.success is False


def test_assassination_guess_structure() -> None:
    """AssassinationGuess correctly stores target and reasoning."""
    guess = AssassinationGuess(
        target_id="player_3", reasoning="Consistent good plays suggest Merlin"
    )
    assert guess.target_id == "player_3"
    assert guess.reasoning != ""


def test_observation_with_different_round_sizes() -> None:
    """build_observation handles different mission sizes across rounds."""
    registrations = [PlayerRegistration(f"Player{i}") for i in range(7)]
    roles = build_role_list(7)
    config = GameConfig(player_count=7, roles=roles)
    setup = perform_setup(config, registrations)
    state = GameState.from_setup(setup)

    player_1_briefing = next(b for b in setup.briefings if b.player.player_id == "player_1")

    # Round 1
    obs_r1 = build_observation(state, "player_1", player_1_briefing.knowledge)
    assert obs_r1.required_team_size == 2
    assert obs_r1.required_fail_count == 1

    # Advance to round 2 (complete first mission)
    leader = state.current_leader
    state.propose_team(leader.player_id, ("player_1", "player_2"))
    votes = {p.player_id: True for p in state.players}
    state.vote_on_team(votes)

    from avalon.game_state import MissionDecision

    decisions = {"player_1": MissionDecision.SUCCESS, "player_2": MissionDecision.SUCCESS}
    state.submit_mission(decisions)

    # Round 2
    obs_r2 = build_observation(state, "player_1", player_1_briefing.knowledge)
    assert obs_r2.required_team_size == 3
    assert obs_r2.required_fail_count == 1


def test_observation_respects_player_count_for_fail_threshold() -> None:
    """build_observation uses correct fail threshold for 7+ players on round 4."""
    registrations = [PlayerRegistration(f"Player{i}") for i in range(7)]
    roles = build_role_list(7)
    config = GameConfig(player_count=7, roles=roles)
    setup = perform_setup(config, registrations)
    state = GameState.from_setup(setup)

    # Fast-forward to round 4
    state.round_number = 4

    player_1_briefing = next(b for b in setup.briefings if b.player.player_id == "player_1")
    observation = build_observation(state, "player_1", player_1_briefing.knowledge)

    # 7-player game, round 4 requires 2 fails
    assert observation.required_fail_count == 2
