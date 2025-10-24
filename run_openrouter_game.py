"""CLI helper for running agent games with OpenRouter API."""

import os
import sys

from avalon.agent_manager import AgentManager
from avalon.config_loader import load_config_file
from avalon.interaction import CLIInteraction, run_interactive_game
from avalon.logging_manager import LoggingManager
from avalon.openrouter_client import OpenRouterClient


def main() -> None:
    """Run an agent game using OpenRouter API."""
    if len(sys.argv) < 2:
        print("Usage: poetry run python run_openrouter_game.py <config-file>")
        print("Example: poetry run python run_openrouter_game.py config-test-openrouter.yaml")
        print()
        print("Make sure to set OPENROUTER_TOKEN environment variable:")
        print("  export OPENROUTER_TOKEN='your-api-key-here'")
        print()
        print("Get your API key from: https://openrouter.ai/keys")
        print("Accept data policy at: https://openrouter.ai/settings/privacy")
        sys.exit(1)

    config_path = sys.argv[1]

    # Check for API key
    if not os.environ.get("OPENROUTER_TOKEN") and not os.environ.get("OPENROUTER_API_KEY"):
        print("ERROR: OPENROUTER_TOKEN environment variable not set")
        print()
        print("Set your OpenRouter API key:")
        print("  export OPENROUTER_TOKEN='your-api-key-here'")
        print()
        print("Get your API key from: https://openrouter.ai/keys")
        print("Accept data policy at: https://openrouter.ai/settings/privacy")
        sys.exit(1)

    # Load configuration
    try:
        setup_config = load_config_file(config_path)
    except Exception as exc:
        print(f"Error loading config file: {exc}")
        sys.exit(1)

    # Check if any agents are configured
    agent_count = sum(1 for reg in setup_config.registrations if reg.player_type.value == "agent")
    human_count = len(setup_config.registrations) - agent_count

    print("\n=== Avalon Agent Game (OpenRouter) ===")
    print(f"Configuration: {config_path}")
    print(f"Players: {human_count} human, {agent_count} agent")
    print()

    # Create OpenRouter client for agents
    try:
        llm_client = OpenRouterClient()
        print("✓ OpenRouter client initialized")
        print(f"AI Model: {llm_client.model_name}")
    except Exception as exc:
        print(f"Error creating OpenRouter client: {exc}")
        sys.exit(1)

    # Create agent manager
    from avalon.setup import perform_setup

    setup = perform_setup(setup_config.game_config, setup_config.registrations)
    agent_mgr = AgentManager.from_setup(setup, llm_client)

    # Create logging manager if enhanced logging is enabled
    log_mgr = (
        LoggingManager(enabled=setup_config.enhanced_logging)
        if setup_config.enhanced_logging
        else None
    )
    if log_mgr and log_mgr.enabled:
        print(f"Enhanced logging enabled: {log_mgr.log_dir}")
        print()

    # Run the game
    try:
        result = run_interactive_game(
            setup_config.game_config,
            io=CLIInteraction(),
            briefing_options=setup_config.briefing_options,
            agent_manager=agent_mgr,
            logging_manager=log_mgr,
            setup=setup,
        )

        # Print final results
        print("\n=== Game Complete ===")
        winner = result.state.final_winner
        winner_text = winner.value.title() if winner else "Unknown"
        print(f"Winner: {winner_text}")
        print(
            f"Final Score: Resistance {result.state.resistance_score} - "
            f"{result.state.minion_score} Minions"
        )
        print(f"Rounds played: {result.state.round_number}")

    except KeyboardInterrupt:
        print("\n\nGame interrupted by user")
        sys.exit(0)
    except Exception as exc:
        print(f"\nError during game: {exc}")
        raise


if __name__ == "__main__":
    main()
