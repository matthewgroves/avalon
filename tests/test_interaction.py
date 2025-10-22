from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from avalon.config import GameConfig
from avalon.enums import Alignment
from avalon.game_state import GamePhase
from avalon.interaction import (
    InteractionEventType,
    InteractionIO,
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


def test_scripted_session_runs_full_resistance_victory() -> None:
    config = GameConfig.default(5)
    names = ["Alice", "Bob", "Carol", "Dave", "Eve"]
    registrations = [PlayerRegistration(name) for name in names]
    seed = 19
    setup = perform_setup(config, registrations, seed=seed)

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

    responses = [
        *names,
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
    result = run_interactive_game(config, io=scripted, seed=seed)
    final_state = result.state

    assert final_state.phase is GamePhase.GAME_OVER
    assert final_state.final_winner is Alignment.RESISTANCE
    assert final_state.assassination is not None
    assert not final_state.assassination.success
    assert final_state.assassination.assassin_id == assassin_id
    assert final_state.assassination.target_id == wrong_target
    assert final_state.resistance_score == 3
    assert not scripted.responses

    hidden_prompts = [
        entry for entry in result.transcript if entry.event is InteractionEventType.HIDDEN_PROMPT
    ]
    assert hidden_prompts
    assert hidden_prompts[-1].message.startswith("Enter Merlin's player id")
    assert hidden_prompts[-1].response == wrong_target

    assert any(
        entry.event is InteractionEventType.OUTPUT and "Game over" in entry.message
        for entry in result.transcript
    )
