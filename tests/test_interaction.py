from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from avalon.config import GameConfig
from avalon.enums import Alignment
from avalon.game_state import GamePhase
from avalon.interaction import (
    BriefingDeliveryMode,
    BriefingOptions,
    InteractionEventType,
    InteractionIO,
    InteractionResult,
    run_interactive_game,
)
from avalon.roles import ROLE_DEFINITIONS, RoleTag
from avalon.setup import PlayerRegistration, perform_setup


@dataclass
class ScriptedIO(InteractionIO):
    responses: List[str]
    writes: List[str]

    def __init__(self, responses: Iterable[str]):
        self.responses = list(responses)
        self.writes = []

    def read(self, prompt: str) -> str:
        return self._consume(prompt)

    def read_hidden(self, prompt: str) -> str:
        return self._consume(prompt)

    def write(self, message: str) -> None:
        self.writes.append(message)

    def _consume(self, prompt: str) -> str:
        self.writes.append(prompt)
        if not self.responses:
            raise AssertionError(f"No scripted response available for prompt: {prompt}")
        return self.responses.pop(0)


def _play_resistance_victory(
    seed: int = 19,
    *,
    briefing_options: BriefingOptions | None = None,
) -> tuple[InteractionResult, ScriptedIO, str]:
    config = GameConfig.default(5)
    names = ["Alice", "Bob", "Carol", "Dave", "Eve"]
    registrations = [PlayerRegistration(name) for name in names]
    setup = perform_setup(config, registrations, seed=seed)
    options = briefing_options or BriefingOptions()

    resistance_ids = [
        player.player_id for player in setup.players if player.alignment is Alignment.RESISTANCE
    ]
    merlin_id = next(
        player.player_id
        for player in setup.players
        if RoleTag.MERLIN in ROLE_DEFINITIONS[player.role].tags
    )
    assassin_id = next(
        player.player_id
        for player in setup.players
        if RoleTag.ASSASSIN in ROLE_DEFINITIONS[player.role].tags
    )

    team_one = " ".join(resistance_ids[:2])
    team_two = " ".join(resistance_ids[:3])
    team_three = " ".join(resistance_ids[:2])
    wrong_target = next(pid for pid in resistance_ids if pid != merlin_id)

    acknowledgement_responses: list[str] = []
    if options.mode is BriefingDeliveryMode.SEQUENTIAL and options.pause_before_each:
        acknowledgement_responses.extend("" for _ in setup.players)
    if options.pause_after_each:
        acknowledgement_responses.extend("" for _ in setup.players)

    responses = [
        *acknowledgement_responses,
        team_one,
        *["y"] * config.player_count,
        *["success"] * 2,
        team_two,
        *["y"] * config.player_count,
        *["success"] * 3,
        team_three,
        *["y"] * config.player_count,
        *["success"] * 2,
        wrong_target,
    ]

    scripted = ScriptedIO(responses)
    result = run_interactive_game(
        config,
        io=scripted,
        seed=seed,
        briefing_options=options,
        registrations=registrations,
    )
    return result, scripted, assassin_id


def test_scripted_session_runs_full_resistance_victory() -> None:
    result, scripted, assassin_id = _play_resistance_victory()
    final_state = result.state

    assert final_state.phase is GamePhase.GAME_OVER
    assert final_state.final_winner is Alignment.RESISTANCE
    assert final_state.assassination is not None
    assert not final_state.assassination.success
    assert final_state.assassination.assassin_id == assassin_id
    assert final_state.resistance_score == 3
    assert not scripted.responses

    hidden_prompts = [
        entry for entry in result.transcript if entry.event is InteractionEventType.HIDDEN_PROMPT
    ]
    assert hidden_prompts
    assert hidden_prompts[-1].message.startswith("Enter Merlin's player id")

    assert any(
        entry.event is InteractionEventType.OUTPUT and "Game over" in entry.message
        for entry in result.transcript
    )


def test_transcript_filters_surface_only_visible_entries() -> None:
    result, _, assassin_id = _play_resistance_victory(seed=19)
    assert result.state.assassination is not None

    public_entries = result.public_transcript()
    assert all(entry.visibility.name.lower() == "public" for entry in public_entries)

    private_entries = [
        entry for entry in result.transcript if entry.visibility.name.lower() == "private"
    ]
    assert private_entries

    first_player_id = result.state.players[0].player_id
    player_entries = result.transcript_for_player(first_player_id)
    assert all(entry in player_entries for entry in public_entries)
    assert len(player_entries) > len(public_entries)

    assassin_entries = result.transcript_for_player(assassin_id)
    assert any("Enter Merlin" in entry.message for entry in assassin_entries)

    res_alignment_entries = result.transcript_for_alignment(Alignment.RESISTANCE)
    minion_alignment_entries = result.transcript_for_alignment(Alignment.MINION)
    assert len(minion_alignment_entries) >= len(res_alignment_entries)


def test_briefings_can_require_acknowledgements() -> None:
    options = BriefingOptions(pause_before_each=True, pause_after_each=True)
    result, scripted, _ = _play_resistance_victory(seed=22, briefing_options=options)

    assert not scripted.responses

    hidden_messages = [
        entry.message
        for entry in result.transcript
        if entry.event is InteractionEventType.HIDDEN_PROMPT
    ]
    assert any("ready to view your briefing" in message for message in hidden_messages)
    assert any("finished reading your briefing" in message for message in hidden_messages)


def test_batch_briefings_emit_batch_instruction() -> None:
    options = BriefingOptions(mode=BriefingDeliveryMode.BATCH)
    result, _, _ = _play_resistance_victory(seed=25, briefing_options=options)

    outputs = [
        entry.message for entry in result.transcript if entry.event is InteractionEventType.OUTPUT
    ]
    assert any("briefings in batch" in message for message in outputs)
