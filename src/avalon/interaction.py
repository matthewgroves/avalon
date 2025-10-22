"""Basic interaction layer for driving Avalon games via prompts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from getpass import getpass
from typing import Protocol, Sequence, Tuple

from .config import GameConfig
from .enums import Alignment
from .events import EventLog, EventVisibility, alignment_audience_tag, player_audience_tag
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


class InteractionEventType(str, Enum):
    """Kinds of interaction events recorded during a session."""

    PROMPT = "prompt"
    HIDDEN_PROMPT = "hidden_prompt"
    OUTPUT = "output"


@dataclass(frozen=True, slots=True)
class InteractionLogEntry:
    """Single prompt/response or output emitted during play."""

    event: InteractionEventType
    message: str
    response: str | None = None
    visibility: EventVisibility = EventVisibility.PUBLIC
    audience: Tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class InteractionResult:
    """Final game state paired with the interaction transcript."""

    state: GameState
    transcript: tuple[InteractionLogEntry, ...]

    def public_transcript(self) -> tuple[InteractionLogEntry, ...]:
        """Return only publicly visible transcript entries."""

        return tuple(
            entry for entry in self.transcript if entry.visibility is EventVisibility.PUBLIC
        )

    def transcript_for_player(
        self,
        player_id: str,
        *,
        include_private: bool = False,
        extra_tags: Sequence[str] | None = None,
    ) -> tuple[InteractionLogEntry, ...]:
        """Return transcript entries visible to the specified player."""

        tags = [player_audience_tag(player_id)]
        if extra_tags:
            tags.extend(extra_tags)
        return _filter_transcript(self.transcript, tags, include_private)

    def transcript_for_alignment(
        self,
        alignment: Alignment | str,
        *,
        include_private: bool = False,
        extra_tags: Sequence[str] | None = None,
    ) -> tuple[InteractionLogEntry, ...]:
        """Return transcript entries visible to the given alignment audience."""

        tags = [alignment_audience_tag(alignment)]
        if extra_tags:
            tags.extend(extra_tags)
        return _filter_transcript(self.transcript, tags, include_private)


YES_VALUES = {"y", "yes", "approve", "a"}
NO_VALUES = {"n", "no", "reject", "r"}
SUCCESS_VALUES = {"s", "success"}
FAIL_VALUES = {"f", "fail"}


def run_interactive_game(
    config: GameConfig,
    *,
    io: InteractionIO | None = None,
    seed: int | None = None,
    event_log: EventLog | None = None,
) -> InteractionResult:
    """Run an Avalon game loop using the provided interaction backend."""

    backend = io or CLIInteraction()
    log: list[InteractionLogEntry] = []

    _write(backend, log, "\n=== Avalon Setup ===")
    registrations = _collect_registrations(config, backend, log)
    setup = perform_setup(config, registrations, seed=seed)
    state = GameState.from_setup(setup)
    state.event_log = event_log or EventLog()
    _announce_roster(state.players, backend, log)

    while state.phase is not GamePhase.GAME_OVER:
        _announce_round(state, backend, log)
        if state.phase is GamePhase.TEAM_PROPOSAL:
            _handle_team_proposal(state, backend, log)
        elif state.phase is GamePhase.TEAM_VOTE:
            _handle_team_vote(state, backend, log)
        elif state.phase is GamePhase.MISSION:
            _handle_mission(state, backend, log)
        elif state.phase is GamePhase.ASSASSINATION_PENDING:
            _handle_assassination(state, backend, log)
        else:  # pragma: no cover - defensive guard
            raise RuntimeError(f"Unhandled phase: {state.phase}")

    _write(backend, log, "")
    winner = state.final_winner.name.title() if state.final_winner else "Unknown"
    _write(backend, log, f"Game over: {winner} victory")
    return InteractionResult(state=state, transcript=tuple(log))


def _prompt_player_count(
    backend: InteractionIO,
    log: list[InteractionLogEntry] | None = None,
) -> int:
    while True:
        prompt = "Enter player count (5-10) [5]: \n"
        if log is None:
            response = backend.read(prompt).strip()
        else:
            response = _read(backend, log, prompt).strip()
        if not response:
            return 5
        if response.isdigit():
            value = int(response)
            if 5 <= value <= 10:
                return value
        if log is None:
            backend.write("Please enter a number between 5 and 10.")
        else:
            _write(backend, log, "Please enter a number between 5 and 10.")


def _collect_registrations(
    config: GameConfig, backend: InteractionIO, log: list[InteractionLogEntry]
) -> list[PlayerRegistration]:
    registrations: list[PlayerRegistration] = []
    for seat in range(1, config.player_count + 1):
        while True:
            name = _read(backend, log, f"Enter display name for player {seat}: \n").strip()
            if name:
                registrations.append(PlayerRegistration(display_name=name))
                break
            _write(backend, log, "Names must be non-empty. Please try again.")
    return registrations


def _announce_roster(
    players: tuple[Player, ...], backend: InteractionIO, log: list[InteractionLogEntry]
) -> None:
    _write(backend, log, "\nRoster:")
    for player in players:
        _write(backend, log, f"  {player.player_id}: {player.display_name}")


def _announce_round(
    state: GameState,
    backend: InteractionIO,
    log: list[InteractionLogEntry],
) -> None:
    _write(
        backend,
        log,
        f"\nRound {state.round_number} • Attempt {state.attempt_number} — "
        f"Resistance {state.resistance_score} / Minions {state.minion_score}",
    )


def _handle_team_proposal(
    state: GameState, backend: InteractionIO, log: list[InteractionLogEntry]
) -> None:
    required_size = state.config.mission_config.team_sizes[state.round_number - 1]
    leader = state.current_leader
    _write(backend, log, f"Leader: {leader.display_name} ({leader.player_id})")

    while True:
        entry = _read(
            backend,
            log,
            f"Select {required_size} player id(s) separated by spaces: \n",
        ).strip()
        team = _parse_team(entry)
        if team is None:
            _write(backend, log, "Please provide valid player identifiers.")
            continue
        try:
            state.propose_team(leader.player_id, team)
            _write(backend, log, f"Proposed team: {', '.join(team)}")
            break
        except InvalidActionError as exc:
            _write(backend, log, f"Invalid team: {exc}")


def _handle_team_vote(
    state: GameState, backend: InteractionIO, log: list[InteractionLogEntry]
) -> None:
    votes: dict[str, bool] = {}
    for player in state.players:
        while True:
            response = (
                _read_hidden(
                    backend,
                    log,
                    f"{player.display_name} vote (approve? y/n): \n",
                    audience=[player_audience_tag(player.player_id)],
                )
                .strip()
                .lower()
            )
            if response in YES_VALUES:
                votes[player.player_id] = True
                break
            if response in NO_VALUES:
                votes[player.player_id] = False
                break
            _write(
                backend,
                log,
                "Please respond with y/n.",
                visibility=EventVisibility.PRIVATE,
                audience=[player_audience_tag(player.player_id)],
            )

    record = state.vote_on_team(votes)
    outcome = "approved" if record.approved else "rejected"
    summary = (
        f"Vote {outcome}. Approvals: {len(record.approvals)} "
        f"• Rejections: {len(record.rejections)}"
    )
    _write(backend, log, summary)


def _handle_mission(
    state: GameState,
    backend: InteractionIO,
    log: list[InteractionLogEntry],
) -> None:
    decisions: dict[str, MissionDecision] = {}
    assert state.current_team is not None  # defensive
    for player_id in state.current_team:
        player = state.players_by_id[player_id]
        while True:
            response = (
                _read_hidden(
                    backend,
                    log,
                    f"{player.display_name} mission decision (success/fail): \n",
                    audience=[player_audience_tag(player_id)],
                )
                .strip()
                .lower()
            )
            if response in SUCCESS_VALUES:
                decisions[player_id] = MissionDecision.SUCCESS
                break
            if response in FAIL_VALUES:
                decisions[player_id] = MissionDecision.FAIL
                break
            _write(
                backend,
                log,
                "Please enter 'success' or 'fail'.",
                visibility=EventVisibility.PRIVATE,
                audience=[player_audience_tag(player_id)],
            )

    record = state.submit_mission(decisions)
    _write(
        backend,
        log,
        f"Mission result: {record.result.value} — fails: {record.fail_count} / required:"
        f" {record.required_fail_count}",
    )


def _handle_assassination(
    state: GameState, backend: InteractionIO, log: list[InteractionLogEntry]
) -> None:
    assassin_ids = state.assassin_ids
    if not assassin_ids:
        _write(backend, log, "No assassin present. Resistance victory confirmed.")
        state.final_winner = Alignment.RESISTANCE
        state.phase = GamePhase.GAME_OVER
        return

    assassin_id = assassin_ids[0]
    assassin = state.players_by_id[assassin_id]
    _write(
        backend,
        log,
        f"Assassination phase: {assassin.display_name} must identify Merlin by player id.",
    )
    while True:
        target_id = _read_hidden(
            backend,
            log,
            "Enter Merlin's player id: \n",
            audience=[player_audience_tag(assassin_id)],
        ).strip()
        if not target_id:
            _write(
                backend,
                log,
                "Target id is required.",
                visibility=EventVisibility.PRIVATE,
                audience=[player_audience_tag(assassin_id)],
            )
            continue
        try:
            record = state.perform_assassination(assassin_id, target_id)
            result = "succeeds" if record.success else "fails"
            _write(backend, log, f"Assassination {result}!")
            break
        except InvalidActionError as exc:
            _write(
                backend,
                log,
                f"Invalid target: {exc}",
                visibility=EventVisibility.PRIVATE,
                audience=[player_audience_tag(assassin_id)],
            )


def _parse_team(entry: str) -> tuple[str, ...] | None:
    tokens = [token for token in entry.replace(",", " ").split(" ") if token]
    return tuple(tokens) if tokens else None


def _read(
    backend: InteractionIO,
    log: list[InteractionLogEntry],
    prompt: str,
    *,
    visibility: EventVisibility = EventVisibility.PUBLIC,
    audience: Sequence[str] | None = None,
) -> str:
    response = backend.read(prompt)
    log.append(
        InteractionLogEntry(
            event=InteractionEventType.PROMPT,
            message=prompt,
            response=response,
            visibility=visibility,
            audience=_audience_tuple(audience),
        )
    )
    return response


def _read_hidden(
    backend: InteractionIO,
    log: list[InteractionLogEntry],
    prompt: str,
    *,
    audience: Sequence[str] | None = None,
) -> str:
    response = backend.read_hidden(prompt)
    log.append(
        InteractionLogEntry(
            event=InteractionEventType.HIDDEN_PROMPT,
            message=prompt,
            response=response,
            visibility=EventVisibility.PRIVATE,
            audience=_audience_tuple(audience),
        )
    )
    return response


def _write(
    backend: InteractionIO,
    log: list[InteractionLogEntry],
    message: str,
    *,
    visibility: EventVisibility = EventVisibility.PUBLIC,
    audience: Sequence[str] | None = None,
) -> None:
    backend.write(message)
    log.append(
        InteractionLogEntry(
            event=InteractionEventType.OUTPUT,
            message=message,
            visibility=visibility,
            audience=_audience_tuple(audience),
        )
    )


def main() -> None:  # pragma: no cover - CLI entry point
    backend = CLIInteraction()
    player_count = _prompt_player_count(backend)
    config = GameConfig.default(player_count)
    run_interactive_game(config, io=backend)


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()


__all__ = [
    "CLIInteraction",
    "InteractionEventType",
    "InteractionIO",
    "InteractionLogEntry",
    "InteractionResult",
    "main",
    "run_interactive_game",
]


def _filter_transcript(
    entries: Sequence[InteractionLogEntry],
    audience_tags: Sequence[str],
    include_private: bool,
) -> tuple[InteractionLogEntry, ...]:
    allowed = set(audience_tags)
    matched: list[InteractionLogEntry] = []
    for entry in entries:
        if entry.visibility is EventVisibility.PUBLIC:
            matched.append(entry)
            continue
        if include_private:
            matched.append(entry)
            continue
        if any(tag in allowed for tag in entry.audience):
            matched.append(entry)
    return tuple(matched)


def _audience_tuple(audience: Sequence[str] | None) -> Tuple[str, ...]:
    return tuple(audience or ())
