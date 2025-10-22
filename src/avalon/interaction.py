"""Basic interaction layer for driving Avalon games via prompts."""

from __future__ import annotations

from dataclasses import dataclass
from getpass import getpass
from typing import Protocol

from .config import GameConfig
from .enums import Alignment
from .exceptions import InvalidActionError
from .game_state import GamePhase, GameState, MissionDecision
from .players import Player
from .setup import PlayerRegistration, perform_setup


class InteractionIO(Protocol):
    """Minimal IO surface for interactive play backends."""

    def read(self, prompt: str) -> str:
        """Return a response to a visible prompt."""
        ...

    def read_hidden(self, prompt: str) -> str:
        """Return a response to a hidden prompt (e.g., votes, mission cards)."""
        ...

    def write(self, message: str) -> None:
        """Display a message to the participant(s)."""
        ...


@dataclass
class CLIInteraction:
    """Console-backed IO using ``input`` and ``getpass``."""

    def read(self, prompt: str) -> str:
        return input(prompt)

    def read_hidden(self, prompt: str) -> str:
        return getpass(prompt)

    def write(self, message: str) -> None:
        print(message)


YES_VALUES = {"y", "yes", "approve", "a"}
NO_VALUES = {"n", "no", "reject", "r"}
SUCCESS_VALUES = {"s", "success"}
FAIL_VALUES = {"f", "fail"}


def run_interactive_game(
    config: GameConfig,
    *,
    io: InteractionIO | None = None,
    seed: int | None = None,
) -> GameState:
    """Run an Avalon game loop using the provided interaction backend."""

    backend = io or CLIInteraction()
    backend.write("\n=== Avalon Setup ===")
    registrations = _collect_registrations(config, backend)
    setup = perform_setup(config, registrations, seed=seed)
    state = GameState.from_setup(setup)
    _announce_roster(state.players, backend)

    while state.phase is not GamePhase.GAME_OVER:
        _announce_round(state, backend)
        if state.phase is GamePhase.TEAM_PROPOSAL:
            _handle_team_proposal(state, backend)
        elif state.phase is GamePhase.TEAM_VOTE:
            _handle_team_vote(state, backend)
        elif state.phase is GamePhase.MISSION:
            _handle_mission(state, backend)
        elif state.phase is GamePhase.ASSASSINATION_PENDING:
            _handle_assassination(state, backend)
        else:  # pragma: no cover - defensive guard
            raise RuntimeError(f"Unhandled phase: {state.phase}")

    backend.write("")
    winner = state.final_winner.name.title() if state.final_winner else "Unknown"
    backend.write(f"Game over: {winner} victory")
    return state


def _prompt_player_count(backend: InteractionIO) -> int:
    while True:
        response = backend.read("Enter player count (5-10) [5]: \n").strip()
        if not response:
            return 5
        if response.isdigit():
            value = int(response)
            if 5 <= value <= 10:
                return value
        backend.write("Please enter a number between 5 and 10.")


def _collect_registrations(config: GameConfig, backend: InteractionIO) -> list[PlayerRegistration]:
    registrations: list[PlayerRegistration] = []
    for seat in range(1, config.player_count + 1):
        while True:
            name = backend.read(f"Enter display name for player {seat}: \n").strip()
            if name:
                registrations.append(PlayerRegistration(display_name=name))
                break
            backend.write("Names must be non-empty. Please try again.")
    return registrations


def _announce_roster(players: tuple[Player, ...], backend: InteractionIO) -> None:
    backend.write("\nRoster:")
    for player in players:
        backend.write(f"  {player.player_id}: {player.display_name}")


def _announce_round(state: GameState, backend: InteractionIO) -> None:
    backend.write(
        f"\nRound {state.round_number} • Attempt {state.attempt_number} — "
        f"Resistance {state.resistance_score} / Minions {state.minion_score}"
    )


def _handle_team_proposal(state: GameState, backend: InteractionIO) -> None:
    required_size = state.config.mission_config.team_sizes[state.round_number - 1]
    leader = state.current_leader
    backend.write(f"Leader: {leader.display_name} ({leader.player_id})")

    while True:
        entry = backend.read(f"Select {required_size} player id(s) separated by spaces: \n").strip()
        team = _parse_team(entry)
        if team is None:
            backend.write("Please provide valid player identifiers.")
            continue
        try:
            state.propose_team(leader.player_id, team)
            backend.write(f"Proposed team: {', '.join(team)}")
            break
        except InvalidActionError as exc:
            backend.write(f"Invalid team: {exc}")


def _handle_team_vote(state: GameState, backend: InteractionIO) -> None:
    votes: dict[str, bool] = {}
    for player in state.players:
        while True:
            response = (
                backend.read_hidden(f"{player.display_name} vote (approve? y/n): \n")
                .strip()
                .lower()
            )
            if response in YES_VALUES:
                votes[player.player_id] = True
                break
            if response in NO_VALUES:
                votes[player.player_id] = False
                break
            backend.write("Please respond with y/n.")

    record = state.vote_on_team(votes)
    outcome = "approved" if record.approved else "rejected"
    backend.write(
        f"Vote {outcome}. Approvals: {len(record.approvals)} • Rejections: {len(record.rejections)}"
    )


def _handle_mission(state: GameState, backend: InteractionIO) -> None:
    decisions: dict[str, MissionDecision] = {}
    assert state.current_team is not None  # defensive
    for player_id in state.current_team:
        player = state.players_by_id[player_id]
        while True:
            response = (
                backend.read_hidden(f"{player.display_name} mission decision (success/fail): \n")
                .strip()
                .lower()
            )
            if response in SUCCESS_VALUES:
                decisions[player_id] = MissionDecision.SUCCESS
                break
            if response in FAIL_VALUES:
                decisions[player_id] = MissionDecision.FAIL
                break
            backend.write("Please enter 'success' or 'fail'.")

    record = state.submit_mission(decisions)
    backend.write(
        f"Mission result: {record.result.value} — fails: {record.fail_count} / required:"
        f" {record.required_fail_count}"
    )


def _handle_assassination(state: GameState, backend: InteractionIO) -> None:
    assassin_ids = state.assassin_ids
    if not assassin_ids:
        backend.write("No assassin present. Resistance victory confirmed.")
        state.final_winner = Alignment.RESISTANCE
        state.phase = GamePhase.GAME_OVER
        return

    assassin_id = assassin_ids[0]
    assassin = state.players_by_id[assassin_id]
    backend.write(
        f"Assassination phase: {assassin.display_name} must identify Merlin by player id."
    )
    while True:
        target_id = backend.read_hidden("Enter Merlin's player id: \n").strip()
        if not target_id:
            backend.write("Target id is required.")
            continue
        try:
            record = state.perform_assassination(assassin_id, target_id)
            result = "succeeds" if record.success else "fails"
            backend.write(f"Assassination {result}!")
            break
        except InvalidActionError as exc:
            backend.write(f"Invalid target: {exc}")


def _parse_team(entry: str) -> tuple[str, ...] | None:
    tokens = [token for token in entry.replace(",", " ").split(" ") if token]
    return tuple(tokens) if tokens else None


def main() -> None:  # pragma: no cover - CLI entry point
    backend = CLIInteraction()
    player_count = _prompt_player_count(backend)
    config = GameConfig.default(player_count)
    run_interactive_game(config, io=backend)


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()


__all__ = ["CLIInteraction", "InteractionIO", "main", "run_interactive_game"]
