from __future__ import annotations

from pathlib import Path

from avalon.config import GameConfig
from avalon.enums import Alignment
from avalon.events import EventLog, GameEventType
from avalon.game_state import GameState, MissionDecision
from avalon.persistence import GameStateSnapshot, restore_game_state, snapshot_game_state
from avalon.setup import PlayerRegistration, perform_setup


def _initial_state(player_count: int = 5, seed: int = 1234) -> GameState:
    config = GameConfig.default(player_count)
    registrations = [PlayerRegistration(f"Player {idx}") for idx in range(1, player_count + 1)]
    setup = perform_setup(config, registrations, seed=seed)
    return GameState.from_setup(setup)


def _team_for_round(state: GameState) -> tuple[str, ...]:
    size = state.config.mission_config.team_sizes[state.round_number - 1]
    return tuple(player.player_id for player in state.players[:size])


def _run_successful_round(state: GameState) -> None:
    team = _team_for_round(state)
    state.propose_team(state.current_leader.player_id, team)
    approvals = {player.player_id: True for player in state.players}
    state.vote_on_team(approvals)
    decisions = {player_id: MissionDecision.SUCCESS for player_id in team}
    state.submit_mission(decisions)


def _build_progressed_state() -> GameState:
    state = _initial_state(seed=99)
    state.event_log = EventLog()
    _run_successful_round(state)
    _run_successful_round(state)
    state.propose_team(state.current_leader.player_id, _team_for_round(state))
    approvals = {
        player.player_id: player.alignment is Alignment.RESISTANCE for player in state.players
    }
    state.vote_on_team(approvals)
    return state


def test_snapshot_round_trip_restores_equivalent_state() -> None:
    state = _build_progressed_state()
    assert state.event_log is not None
    snapshot = snapshot_game_state(state)
    restored = restore_game_state(snapshot)

    assert restored.phase is state.phase
    assert restored.round_number == state.round_number
    assert restored.attempt_number == state.attempt_number
    assert restored.leader_index == state.leader_index
    assert restored.resistance_score == state.resistance_score
    assert restored.minion_score == state.minion_score
    assert restored.votes == state.votes
    assert restored.missions == state.missions
    assert restored.assassination == state.assassination
    assert restored.current_team == state.current_team
    assert restored.consecutive_rejections == state.consecutive_rejections
    assert restored.provisional_winner == state.provisional_winner
    assert restored.final_winner == state.final_winner
    assert restored.seed == state.seed
    assert restored.event_log is not None
    assert restored.event_log.events == state.event_log.events


def test_snapshot_can_be_saved_and_loaded(tmp_path: Path) -> None:
    state = _build_progressed_state()
    assert state.event_log is not None
    snapshot = GameStateSnapshot.from_game_state(state)
    path = tmp_path / "game_state.json"
    snapshot.save(path)

    loaded = GameStateSnapshot.load(path)
    assert loaded.payload == snapshot.payload

    restored = loaded.restore()
    assert restored.votes == state.votes
    assert restored.missions == state.missions
    assert restored.event_log is not None
    event_types = [event.type for event in restored.event_log.events]
    assert GameEventType.TEAM_VOTE_RECORDED in event_types
