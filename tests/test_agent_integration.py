"""Integration tests for agent players in full games."""

from __future__ import annotations

from avalon.agent_manager import AgentManager
from avalon.config import GameConfig
from avalon.enums import PlayerType
from avalon.game_state import GamePhase
from avalon.interaction import run_interactive_game
from avalon.mock_llm_client import create_simple_agent_strategy
from avalon.roles import build_role_list
from avalon.setup import PlayerRegistration, perform_setup


def test_all_agent_game_completes() -> None:
    """A game with all agent players completes successfully."""
    # Create 5 agent players
    registrations = [
        PlayerRegistration(f"Agent{i}", player_type=PlayerType.AGENT) for i in range(1, 6)
    ]

    roles = build_role_list(5)
    config = GameConfig(player_count=5, roles=roles, random_seed=42)

    # Create agent manager with simple strategy
    setup = perform_setup(config, registrations)
    mock_client = create_simple_agent_strategy(always_approve=True, always_succeed=True)
    agent_mgr = AgentManager.from_setup(setup, mock_client)

    # Run game with agent manager
    result = run_interactive_game(config, registrations=registrations, agent_manager=agent_mgr)

    # Game should complete
    assert result.state.phase == GamePhase.GAME_OVER
    assert result.state.final_winner is not None


def test_mixed_human_agent_game() -> None:
    """A game with mix of human and agent players works correctly."""
    # 2 humans, 3 agents
    registrations = [
        PlayerRegistration("Human1", player_type=PlayerType.HUMAN),
        PlayerRegistration("Human2", player_type=PlayerType.HUMAN),
        PlayerRegistration("Agent1", player_type=PlayerType.AGENT),
        PlayerRegistration("Agent2", player_type=PlayerType.AGENT),
        PlayerRegistration("Agent3", player_type=PlayerType.AGENT),
    ]

    roles = build_role_list(5)
    config = GameConfig(player_count=5, roles=roles, random_seed=42)

    # Create agent manager
    setup = perform_setup(config, registrations)
    mock_client = create_simple_agent_strategy(always_approve=True, always_succeed=True)
    _agent_mgr = AgentManager.from_setup(setup, mock_client)

    # Note: This test would need scripted human inputs to complete
    # For now, just verify setup works
    assert len([p for p in setup.players if p.is_agent]) == 3
    assert len([p for p in setup.players if p.is_human]) == 2


def test_agent_manager_identifies_agents_correctly() -> None:
    """AgentManager correctly identifies agent vs human players."""
    registrations = [
        PlayerRegistration("Human1", player_type=PlayerType.HUMAN),
        PlayerRegistration("Agent1", player_type=PlayerType.AGENT),
        PlayerRegistration("Human2", player_type=PlayerType.HUMAN),
        PlayerRegistration("Agent2", player_type=PlayerType.AGENT),
        PlayerRegistration("Agent3", player_type=PlayerType.AGENT),
    ]

    roles = build_role_list(5)
    config = GameConfig(player_count=5, roles=roles)
    setup = perform_setup(config, registrations)

    mock_client = create_simple_agent_strategy()
    agent_mgr = AgentManager.from_setup(setup, mock_client)

    # Create a game state
    from avalon.game_state import GameState

    state = GameState.from_setup(setup)

    # Check agent identification
    assert not agent_mgr.is_agent("player_1", state)  # Human1
    assert agent_mgr.is_agent("player_2", state)  # Agent1
    assert not agent_mgr.is_agent("player_3", state)  # Human2
    assert agent_mgr.is_agent("player_4", state)  # Agent2
    assert agent_mgr.is_agent("player_5", state)  # Agent3


def test_agent_manager_generates_decisions() -> None:
    """AgentManager can generate all decision types."""
    registrations = [
        PlayerRegistration(f"Agent{i}", player_type=PlayerType.AGENT) for i in range(5)
    ]

    roles = build_role_list(5)
    config = GameConfig(player_count=5, roles=roles)
    setup = perform_setup(config, registrations)

    mock_client = create_simple_agent_strategy(always_approve=True, always_succeed=True)
    agent_mgr = AgentManager.from_setup(setup, mock_client)

    from avalon.game_state import GameState

    state = GameState.from_setup(setup)

    # Test team proposal
    proposal = agent_mgr.propose_team("player_1", state)
    assert len(proposal.team) == 2  # First mission requires 2 players

    # Test vote
    vote = agent_mgr.vote_on_team("player_1", state)
    assert vote.approve is True

    # Test mission action
    action = agent_mgr.execute_mission("player_1", state)
    assert action.success is True

    # Test assassination guess
    guess = agent_mgr.guess_merlin("player_1", state)
    assert guess.target_id in [p.player_id for p in state.players]
