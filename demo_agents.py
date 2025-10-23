"""Demo script showing agent players in action."""

from avalon.agent_manager import AgentManager
from avalon.config import GameConfig
from avalon.enums import PlayerType
from avalon.interaction import CLIInteraction, run_interactive_game
from avalon.mock_llm_client import create_simple_agent_strategy
from avalon.roles import build_role_list
from avalon.setup import PlayerRegistration, perform_setup


def demo_all_agent_game() -> None:
    """Run a full game with all agent players."""
    print("\n=== Demo: All-Agent Avalon Game ===\n")

    # Create 5 agent players
    registrations = [
        PlayerRegistration("AliceBot", player_type=PlayerType.AGENT),
        PlayerRegistration("BobBot", player_type=PlayerType.AGENT),
        PlayerRegistration("CarolBot", player_type=PlayerType.AGENT),
        PlayerRegistration("DaveBot", player_type=PlayerType.AGENT),
        PlayerRegistration("EveBot", player_type=PlayerType.AGENT),
    ]

    # Setup game with roles
    roles = build_role_list(5)
    config = GameConfig(player_count=5, roles=roles, random_seed=42)

    # Create agent manager with simple strategy
    # Agents always approve teams and play success cards
    setup = perform_setup(config, registrations)
    mock_client = create_simple_agent_strategy(always_approve=True, always_succeed=True)
    agent_mgr = AgentManager.from_setup(setup, mock_client)

    # Run the game
    result = run_interactive_game(
        config,
        io=CLIInteraction(),
        registrations=registrations,
        agent_manager=agent_mgr,
    )

    # Print results
    print("\n=== Game Complete ===")
    print(f"Winner: {result.state.final_winner}")
    print(
        f"Final Score: Resistance {result.state.resistance_score} - "
        f"{result.state.minion_score} Minions"
    )
    print(f"Rounds played: {result.state.round_number}")
    print(f"Total transcript entries: {len(result.transcript)}")


if __name__ == "__main__":
    demo_all_agent_game()
