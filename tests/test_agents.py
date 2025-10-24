"""Tests for agent interfaces and observation state construction."""

from __future__ import annotations

from avalon.agents import (
    AgentObservation,
    AssassinationGuess,
    MissionAction,
    TeamProposal,
    VoteDecision,
    build_observation,
)
from avalon.config import GameConfig
from avalon.enums import Alignment
from avalon.game_state import GamePhase, GameState
from avalon.mock_llm_client import MockLLMClient, create_simple_agent_strategy
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
        true_reasoning="Choosing trusted players based on voting patterns",
        public_reasoning="These players work well together",
    )
    assert len(proposal.team) == 3
    assert "player_1" in proposal.team
    assert proposal.true_reasoning != ""
    assert proposal.public_reasoning != ""


def test_vote_decision_structure() -> None:
    """VoteDecision correctly stores approval and reasoning."""
    approve = VoteDecision(
        approve=True,
        true_reasoning="Team composition looks good",
        public_reasoning="I trust this team",
    )
    reject = VoteDecision(
        approve=False,
        true_reasoning="Suspicious behavior from player_3",
        public_reasoning="This team doesn't feel right",
    )

    assert approve.approve is True
    assert reject.approve is False
    assert approve.true_reasoning != ""
    assert approve.public_reasoning != ""


def test_mission_action_structure() -> None:
    """MissionAction correctly stores card choice and reasoning."""
    success_action = MissionAction(
        success=True,
        true_reasoning="Resistance player",
        public_reasoning="Supporting the team",
    )
    fail_action = MissionAction(
        success=False,
        true_reasoning="Sabotaging mission",
        public_reasoning="I played success but someone failed",
    )

    assert success_action.success is True
    assert fail_action.success is False


def test_assassination_guess_structure() -> None:
    """AssassinationGuess correctly stores target and reasoning."""
    guess = AssassinationGuess(
        target_id="player_3",
        true_reasoning="Consistent good plays suggest Merlin",
        public_reasoning="They seemed too knowledgeable",
    )
    assert guess.target_id == "player_3"
    assert guess.true_reasoning != ""
    assert guess.public_reasoning != ""


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


def test_mock_llm_client_scripted_responses() -> None:
    """MockLLMClient returns scripted responses in sequence."""
    mock_client = MockLLMClient(
        team_proposals=[
            TeamProposal(
                ("player_1", "player_2"),
                true_reasoning="First proposal",
                public_reasoning="Team one",
            ),
            TeamProposal(
                ("player_3", "player_4"),
                true_reasoning="Second proposal",
                public_reasoning="Team two",
            ),
        ],
        vote_decisions=[
            VoteDecision(True, "Approve first", "Looks good"),
            VoteDecision(False, "Reject second", "Not good"),
        ],
        mission_actions=[
            MissionAction(True, "Success first", "Supporting"),
            MissionAction(False, "Fail second", "Sabotaging"),
        ],
    )

    # Setup basic observation
    registrations = [PlayerRegistration(f"Player{i}") for i in range(5)]
    roles = build_role_list(5)
    config = GameConfig(player_count=5, roles=roles)
    setup = perform_setup(config, registrations)
    state = GameState.from_setup(setup)
    player_1_briefing = next(b for b in setup.briefings if b.player.player_id == "player_1")
    observation = build_observation(state, "player_1", player_1_briefing.knowledge)

    # Test scripted responses
    proposal1 = mock_client.propose_team(observation)
    assert proposal1.team == ("player_1", "player_2")
    assert proposal1.true_reasoning == "First proposal"

    proposal2 = mock_client.propose_team(observation)
    assert proposal2.team == ("player_3", "player_4")
    assert proposal2.true_reasoning == "Second proposal"

    vote1 = mock_client.vote_on_team(observation)
    assert vote1.approve is True

    vote2 = mock_client.vote_on_team(observation)
    assert vote2.approve is False

    action1 = mock_client.execute_mission(observation)
    assert action1.success is True

    action2 = mock_client.execute_mission(observation)
    assert action2.success is False


def test_mock_llm_client_strategy_functions() -> None:
    """MockLLMClient can use strategy functions instead of scripted responses."""

    def custom_propose(obs: AgentObservation) -> TeamProposal:
        # Always include the agent themselves
        team = (obs.player_id,) + obs.all_player_ids[1 : obs.required_team_size]
        return TeamProposal(
            team=team,
            true_reasoning="Always include self",
            public_reasoning="Including myself for reliability",
        )

    mock_client = MockLLMClient(propose_team_fn=custom_propose)

    registrations = [PlayerRegistration(f"Player{i}") for i in range(5)]
    roles = build_role_list(5)
    config = GameConfig(player_count=5, roles=roles)
    setup = perform_setup(config, registrations)
    state = GameState.from_setup(setup)
    player_1_briefing = next(b for b in setup.briefings if b.player.player_id == "player_1")
    observation = build_observation(state, "player_1", player_1_briefing.knowledge)

    proposal = mock_client.propose_team(observation)
    assert "player_1" in proposal.team
    assert proposal.true_reasoning == "Always include self"


def test_create_simple_agent_strategy() -> None:
    """create_simple_agent_strategy creates a basic mock agent."""
    mock_client = create_simple_agent_strategy(always_approve=True, always_succeed=True)

    registrations = [PlayerRegistration(f"Player{i}") for i in range(5)]
    roles = build_role_list(5)
    config = GameConfig(player_count=5, roles=roles)
    setup = perform_setup(config, registrations)
    state = GameState.from_setup(setup)
    player_1_briefing = next(b for b in setup.briefings if b.player.player_id == "player_1")
    observation = build_observation(state, "player_1", player_1_briefing.knowledge)

    # Test all decision methods work
    proposal = mock_client.propose_team(observation)
    assert len(proposal.team) == observation.required_team_size

    vote = mock_client.vote_on_team(observation)
    assert vote.approve is True

    action = mock_client.execute_mission(observation)
    assert action.success is True

    guess = mock_client.guess_merlin(observation)
    assert guess.target_id in observation.all_player_ids


def test_mock_llm_client_fallback_behavior() -> None:
    """MockLLMClient provides sensible defaults when no responses scripted."""
    mock_client = MockLLMClient()

    registrations = [PlayerRegistration(f"Player{i}") for i in range(5)]
    roles = build_role_list(5)
    config = GameConfig(player_count=5, roles=roles)
    setup = perform_setup(config, registrations)
    state = GameState.from_setup(setup)
    player_1_briefing = next(b for b in setup.briefings if b.player.player_id == "player_1")
    observation = build_observation(state, "player_1", player_1_briefing.knowledge)

    # Should return defaults without errors
    proposal = mock_client.propose_team(observation)
    assert len(proposal.team) == observation.required_team_size

    vote = mock_client.vote_on_team(observation)
    assert isinstance(vote.approve, bool)

    action = mock_client.execute_mission(observation)
    assert isinstance(action.success, bool)

    guess = mock_client.guess_merlin(observation)
    assert guess.target_id in observation.all_player_ids
