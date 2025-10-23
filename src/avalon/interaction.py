"""Basic interaction layer for driving Avalon games via prompts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from getpass import getpass
from typing import Any, Protocol, Sequence, Tuple

from .config import GameConfig
from .enums import Alignment, PlayerType, RoleType
from .events import EventLog, EventVisibility, alignment_audience_tag, player_audience_tag
from .exceptions import InvalidActionError
from .game_state import GamePhase, GameState, MissionDecision
from .players import Player
from .roles import ROLE_DEFINITIONS, build_role_list
from .setup import PlayerRegistration, SetupResult, perform_setup


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


class BriefingDeliveryMode(str, Enum):
    """Supported delivery patterns for setup briefings."""

    SEQUENTIAL = "sequential"
    BATCH = "batch"


@dataclass(frozen=True, slots=True)
class BriefingOptions:
    """Tunable options controlling how setup briefings are surfaced."""

    mode: BriefingDeliveryMode = BriefingDeliveryMode.SEQUENTIAL
    pause_before_each: bool = False
    pause_after_each: bool = False


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
    briefing_options: BriefingOptions | None = None,
    registrations: Sequence[PlayerRegistration] | None = None,
    agent_manager: Any | None = None,  # AgentManager, avoiding circular import
) -> InteractionResult:
    """Run an Avalon game loop using the provided interaction backend.

    Args:
        config: Game configuration.
        io: Interaction backend (defaults to CLI).
        seed: Random seed for reproducible games.
        event_log: Event log for tracking game events.
        briefing_options: Briefing delivery configuration.
        registrations: Pre-configured player registrations.
        agent_manager: Optional agent manager for LLM agent players.

    Returns:
        InteractionResult with final state and transcript.
    """

    backend = io or CLIInteraction()
    log: list[InteractionLogEntry] = []
    delivery_options = briefing_options or BriefingOptions()

    _write(backend, log, "\n=== Avalon Setup ===")
    if registrations is None:
        registrations = _collect_registrations(config, backend, log)
    setup = perform_setup(config, registrations, seed=seed)
    state = GameState.from_setup(setup)
    state.event_log = event_log or EventLog()
    _announce_roster(state.players, backend, log)
    _deliver_private_briefings(setup, backend, log, delivery_options)

    # Track public statements from agents for observation building
    public_statements: list[Tuple[str, str, str]] = []

    # Pass reference to agent manager if present
    if agent_manager:
        agent_manager.set_public_statements(public_statements)

    while state.phase is not GamePhase.GAME_OVER:
        _announce_round(state, backend, log)
        if state.phase is GamePhase.TEAM_PROPOSAL:
            _handle_team_proposal(state, backend, log, agent_manager, public_statements)
        elif state.phase is GamePhase.TEAM_VOTE:
            _handle_team_vote(state, backend, log, agent_manager, public_statements)
        elif state.phase is GamePhase.MISSION:
            _handle_mission(state, backend, log, agent_manager, public_statements)
        elif state.phase is GamePhase.ASSASSINATION_PENDING:
            _handle_assassination(state, backend, log, agent_manager, public_statements)
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
        # Prompt for name
        while True:
            name = _read(backend, log, f"Enter display name for player {seat}: \n").strip()
            if name:
                break
            _write(backend, log, "Names must be non-empty. Please try again.")

        # Prompt for player type
        while True:
            type_input = (
                _read(
                    backend,
                    log,
                    f"Is {name} a human or agent player? (h/a) [h]: \n",
                )
                .strip()
                .lower()
            )
            if not type_input or type_input == "h" or type_input == "human":
                player_type = PlayerType.HUMAN
                break
            elif type_input == "a" or type_input == "agent":
                player_type = PlayerType.AGENT
                break
            else:
                _write(backend, log, "Please enter 'h' for human or 'a' for agent.")

        registrations.append(PlayerRegistration(display_name=name, player_type=player_type))

    return registrations


def _prompt_optional_roles(
    backend: InteractionIO,
    log: list[InteractionLogEntry],
) -> list[RoleType]:
    """Prompt user to select optional special characters to include."""
    _write(
        backend,
        log,
        "\nOptional special characters (Merlin and Assassin are always included):",
    )
    _write(backend, log, "  1. Percival")
    _write(backend, log, "  2. Morgana")
    _write(backend, log, "  3. Mordred")
    _write(backend, log, "  4. Oberon")
    _write(
        backend,
        log,
        "\nEnter numbers separated by spaces (e.g., '2 3' for Morgana and Mordred), "
        "or press Enter to skip:",
    )

    response = _read(backend, log, "> ").strip()
    if not response:
        return []

    role_map = {
        "1": RoleType.PERCIVAL,
        "2": RoleType.MORGANA,
        "3": RoleType.MORDRED,
        "4": RoleType.OBERON,
    }

    tokens = response.replace(",", " ").split()
    selected_roles: list[RoleType] = []

    for token in tokens:
        if token in role_map:
            role = role_map[token]
            if role not in selected_roles:
                selected_roles.append(role)
        else:
            _write(backend, log, f"  Warning: ignoring invalid selection '{token}'")

    if selected_roles:
        names = [role.value.replace("_", " ").title() for role in selected_roles]
        _write(backend, log, f"Selected: {', '.join(names)}")
    else:
        _write(backend, log, "No optional roles selected.")

    return selected_roles


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
    state: GameState,
    backend: InteractionIO,
    log: list[InteractionLogEntry],
    agent_manager: Any | None = None,
    public_statements: list[Tuple[str, str, str]] | None = None,
) -> None:
    required_size = state.config.mission_config.team_sizes[state.round_number - 1]
    leader = state.current_leader
    _write(backend, log, f"Leader: {leader.display_name} ({leader.player_id})")

    # Check if leader is an agent
    if agent_manager and agent_manager.is_agent(leader.player_id, state):
        _write(backend, log, f"  [Agent {leader.display_name} is selecting team...]")
        proposal = agent_manager.propose_team(leader.player_id, state)
        team = proposal.team
        # Display public reasoning (not private!)
        if proposal.public_reasoning:
            _write(backend, log, f'  {leader.display_name} says: "{proposal.public_reasoning}"')
            # Track public statement for other agents
            if public_statements is not None:
                public_statements.append(
                    (leader.player_id, "team_proposal", proposal.public_reasoning)
                )
        try:
            state.propose_team(leader.player_id, team)
            _write(backend, log, f"Proposed team: {', '.join(team)}")
            return
        except InvalidActionError as exc:
            _write(backend, log, f"Agent error: {exc}. Falling back to human input.")
            # Fall through to human input

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
    state: GameState,
    backend: InteractionIO,
    log: list[InteractionLogEntry],
    agent_manager: Any | None = None,
    public_statements: list[Tuple[str, str, str]] | None = None,
) -> None:
    votes: dict[str, bool] = {}
    for player in state.players:
        # Check if player is an agent
        if agent_manager and agent_manager.is_agent(player.player_id, state):
            _write(backend, log, f"  [Agent {player.display_name} is voting...]")
            decision = agent_manager.vote_on_team(player.player_id, state)
            votes[player.player_id] = decision.approve
            vote_str = "APPROVE" if decision.approve else "REJECT"
            _write(backend, log, f"  {player.display_name}: {vote_str}")
            # Display public reasoning (not private!)
            if decision.public_reasoning:
                _write(backend, log, f'    Says: "{decision.public_reasoning}"')
                # Track public statement for other agents
                if public_statements is not None:
                    public_statements.append((player.player_id, "vote", decision.public_reasoning))
            continue

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
    agent_manager: Any | None = None,
    public_statements: list[Tuple[str, str, str]] | None = None,
) -> None:
    decisions: dict[str, MissionDecision] = {}
    assert state.current_team is not None  # defensive
    mission_team = list(state.current_team)  # Save team before it's cleared
    for player_id in state.current_team:
        player = state.players_by_id[player_id]

        # Check if player is an agent
        if agent_manager and agent_manager.is_agent(player_id, state):
            _write(backend, log, f"  [Agent {player.display_name} is submitting card...]")
            action = agent_manager.execute_mission(player_id, state)
            decisions[player_id] = (
                MissionDecision.SUCCESS if action.success else MissionDecision.FAIL
            )
            # Display public reasoning (not private!) - shown after mission resolves
            # Note: We'll store this to display after the mission for hidden card aspect
            if action.public_reasoning:
                # Store for later display
                if public_statements is not None:
                    public_statements.append((player_id, "mission", action.public_reasoning))
            continue

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

    # Now display agent public reasoning about their mission actions
    if public_statements and mission_team:
        mission_statements = [
            (pid, dtype, stmt)
            for pid, dtype, stmt in public_statements
            if dtype == "mission" and pid in mission_team
        ]
        if mission_statements:
            _write(backend, log, "\nPlayers explain their actions:")
            for player_id, _, statement in mission_statements:
                player_name = state.players_by_id[player_id].display_name
                _write(backend, log, f'  {player_name}: "{statement}"')


def _handle_assassination(
    state: GameState,
    backend: InteractionIO,
    log: list[InteractionLogEntry],
    agent_manager: Any | None = None,
    public_statements: list[Tuple[str, str, str]] | None = None,
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

    # Check if assassin is an agent
    if agent_manager and agent_manager.is_agent(assassin_id, state):
        _write(backend, log, f"  [Agent {assassin.display_name} is guessing Merlin...]")
        guess = agent_manager.guess_merlin(assassin_id, state)
        target_id = guess.target_id
        # Display public reasoning (not private!)
        if guess.public_reasoning:
            _write(backend, log, f'  {assassin.display_name} says: "{guess.public_reasoning}"')
            # Track public statement for other agents
            if public_statements is not None:
                public_statements.append((assassin_id, "assassination", guess.public_reasoning))
        try:
            record = state.perform_assassination(assassin_id, target_id)
            result = "succeeds" if record.success else "fails"
            _write(backend, log, f"Assassination {result}!")
            return
        except InvalidActionError as exc:
            _write(backend, log, f"Agent error: {exc}. Falling back to human input.")
            # Fall through to human input

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


def _deliver_private_briefings(
    setup: SetupResult,
    backend: InteractionIO,
    log: list[InteractionLogEntry],
    options: BriefingOptions,
) -> None:
    if options.mode is BriefingDeliveryMode.SEQUENTIAL:
        _write(
            backend,
            log,
            "\nDistributing private briefings one player at a time. "
            "Only the addressed player should view the screen.",
        )
    else:
        _write(
            backend,
            log,
            "\nDistributing private briefings in batch. "
            "Moderators should share each briefing with the appropriate player only.",
        )

    players_by_id = {player.player_id: player for player in setup.players}
    for briefing in setup.briefings:
        player = briefing.player

        # Skip displaying briefings for agent players
        if player.is_agent:
            continue

        definition = ROLE_DEFINITIONS[player.role]
        lines = [
            f"Private briefing for {player.display_name} ({player.player_id})",
            f"Role: {player.role.value.replace('_', ' ').title()}",
            f"Alignment: {definition.alignment.value.title()}",
        ]
        knowledge = briefing.knowledge
        if knowledge.visible_player_ids:
            visible_names = []
            for player_id in knowledge.visible_player_ids:
                known_player = players_by_id[player_id]
                known_role = known_player.role
                known_def = ROLE_DEFINITIONS[known_role]
                # Show detailed info about what we know
                visible_names.append(
                    f"{known_player.display_name} ({player_id}) - "
                    f"{known_role.value.replace('_', ' ').title()} "
                    f"[{known_def.alignment.value.title()}]"
                )
            lines.append("You learn the identities of: " + ", ".join(visible_names))
        if knowledge.ambiguous_player_id_groups:
            group_descriptions = []
            for group in knowledge.ambiguous_player_id_groups:
                group_names = []
                # Determine what roles are possible for this ambiguous group
                possible_roles = set()
                for player_id in group:
                    known_player = players_by_id[player_id]
                    possible_roles.add(known_player.role.value.replace("_", " ").title())

                for player_id in group:
                    known_player = players_by_id[player_id]
                    group_names.append(f"{known_player.display_name} ({player_id})")

                # Add explanation of what each could be
                roles_desc = " or ".join(sorted(possible_roles))
                group_descriptions.append(
                    f"[{', '.join(group_names)}] - each could be: {roles_desc}"
                )
            lines.append("Ambiguous intel: " + " | ".join(group_descriptions))
        if not knowledge.has_information:
            lines.append("No additional intel is provided beyond your role.")

        if options.mode is BriefingDeliveryMode.SEQUENTIAL:
            _write(
                backend,
                log,
                f"\nPlease invite {player.display_name} to view their briefing now.",
            )
            if options.pause_before_each:
                _read_hidden(
                    backend,
                    log,
                    f"{player.display_name}, press enter when you're ready to view "
                    "your briefing.\n",
                    audience=[player_audience_tag(player.player_id)],
                )

        _write(
            backend,
            log,
            "\n".join(lines),
            visibility=EventVisibility.PRIVATE,
            audience=[player_audience_tag(player.player_id)],
        )

        if options.pause_after_each:
            _read_hidden(
                backend,
                log,
                f"{player.display_name}, press enter once you've finished reading your briefing.\n",
                audience=[player_audience_tag(player.player_id)],
            )

        if options.mode is BriefingDeliveryMode.SEQUENTIAL:
            _write(
                backend,
                log,
                f"Briefing complete for {player.display_name}.",
            )


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


def main() -> None:  # pragma: no cover - CLI entry point
    """Run the interactive Avalon CLI.

    Supports two modes:
    1. Interactive setup: prompts for all game configuration
    2. Config file: pass --config <path> to load from YAML
    """
    import sys

    from .config_loader import load_config_file

    backend = CLIInteraction()

    # Check for config file argument
    config_path = None
    if len(sys.argv) > 1:
        if sys.argv[1] in ("--config", "-c") and len(sys.argv) > 2:
            config_path = sys.argv[2]
        elif not sys.argv[1].startswith("-"):
            config_path = sys.argv[1]

    if config_path:
        # Load from config file
        try:
            setup_config = load_config_file(config_path)
            backend.write(f"Loaded configuration from {config_path}")
            backend.write(
                f"Game: {setup_config.game_config.player_count} players, "
                f"{len(setup_config.game_config.roles)} roles"
            )
            run_interactive_game(
                setup_config.game_config,
                io=backend,
                seed=setup_config.game_config.random_seed,
                briefing_options=setup_config.briefing_options,
                registrations=setup_config.registrations,
            )
        except (FileNotFoundError, Exception) as exc:
            backend.write(f"Error loading config: {exc}")
            sys.exit(1)
    else:
        # Interactive setup
        player_count = _prompt_player_count(backend)

        # Prompt for optional role selection
        log: list[InteractionLogEntry] = []
        optional_roles = _prompt_optional_roles(backend, log)

        # Build role list
        roles = build_role_list(
            player_count, optional_roles=optional_roles if optional_roles else None
        )
        config = GameConfig(player_count=player_count, roles=roles)

        run_interactive_game(config, io=backend)


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()


__all__ = [
    "BriefingDeliveryMode",
    "BriefingOptions",
    "CLIInteraction",
    "InteractionEventType",
    "InteractionIO",
    "InteractionLogEntry",
    "InteractionResult",
    "main",
    "run_interactive_game",
]
