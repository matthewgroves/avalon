from __future__ import annotations

import pytest

from avalon.config import GameConfig
from avalon.enums import Alignment, RoleType
from avalon.exceptions import InvalidActionError
from avalon.game_state import (
    GamePhase,
    GameState,
    MissionDecision,
    MissionRecord,
    MissionResult,
)
from avalon.setup import PlayerRegistration, perform_setup


def _default_state(player_count: int, seed: int = 11) -> GameState:
    config = GameConfig.default(player_count)
    registrations = [PlayerRegistration(f"Player {i}") for i in range(1, player_count + 1)]
    setup = perform_setup(config, registrations, seed=seed)
    return GameState.from_setup(setup)


def _team_members(state: GameState, size: int) -> tuple[str, ...]:
    return tuple(player.player_id for player in state.players[:size])


def _team_with_minion(state: GameState, size: int) -> tuple[str, ...]:
    minion_ids = [
        player.player_id for player in state.players if player.alignment is Alignment.MINION
    ]
    resistance_ids = [
        player.player_id for player in state.players if player.alignment is Alignment.RESISTANCE
    ]
    if not minion_ids:
        raise AssertionError("expected at least one minion in the setup")
    team: list[str] = [minion_ids[0]]
    for pid in resistance_ids:
        if len(team) == size:
            break
        team.append(pid)
    for pid in minion_ids[1:]:
        if len(team) == size:
            break
        if pid not in team:
            team.append(pid)
    if len(team) != size:
        raise AssertionError("could not build team containing a minion")
    return tuple(team)


def _team_with_minions(state: GameState, size: int, minion_count: int) -> tuple[str, ...]:
    minion_ids = [
        player.player_id for player in state.players if player.alignment is Alignment.MINION
    ]
    resistance_ids = [
        player.player_id for player in state.players if player.alignment is Alignment.RESISTANCE
    ]
    if len(minion_ids) < minion_count:
        raise AssertionError("requested more minions than are available")
    team: list[str] = list(minion_ids[:minion_count])
    for pid in resistance_ids:
        if len(team) == size:
            break
        if pid not in team:
            team.append(pid)
    for pid in minion_ids[minion_count:]:
        if len(team) == size:
            break
        if pid not in team:
            team.append(pid)
    if len(team) != size:
        raise AssertionError("unable to construct team with requested minions")
    return tuple(team)


def _team_of_resistance(state: GameState, size: int) -> tuple[str, ...]:
    team = [
        player.player_id for player in state.players if player.alignment is Alignment.RESISTANCE
    ][:size]
    if len(team) != size:
        raise AssertionError("not enough resistance players available")
    return tuple(team)


def _approve_team(
    state: GameState,
    team: tuple[str, ...],
    votes: dict[str, bool] | None = None,
) -> None:
    state.propose_team(state.current_leader.player_id, team)
    vote_map = votes or {player.player_id: True for player in state.players}
    record = state.vote_on_team(vote_map)
    assert record.approved


def _run_mission(
    state: GameState,
    team: tuple[str, ...],
    decisions: dict[str, MissionDecision],
    votes: dict[str, bool] | None = None,
) -> MissionRecord:
    _approve_team(state, team, votes=votes)
    if set(decisions.keys()) != set(team):
        raise AssertionError("mission decisions must cover the approved team exactly")
    assert state.phase is GamePhase.MISSION
    return state.submit_mission(decisions)


def _reach_round_four_state(seed: int = 37) -> GameState:
    state = _default_state(7, seed=seed)
    mission_sizes = state.config.mission_config.team_sizes

    team_one = _team_members(state, mission_sizes[0])
    _run_mission(state, team_one, {pid: MissionDecision.SUCCESS for pid in team_one})

    team_two = _team_members(state, mission_sizes[1])
    _run_mission(state, team_two, {pid: MissionDecision.SUCCESS for pid in team_two})

    team_three = _team_with_minion(state, mission_sizes[2])
    decisions = {pid: MissionDecision.SUCCESS for pid in team_three}
    failing_minion = next(
        pid for pid in team_three if state.players_by_id[pid].alignment is Alignment.MINION
    )
    decisions[failing_minion] = MissionDecision.FAIL
    _run_mission(state, team_three, decisions)

    assert state.round_number == 4
    assert state.phase is GamePhase.TEAM_PROPOSAL
    assert state.resistance_score == 2
    assert state.minion_score == 1
    return state


def test_initial_state_configuration_matches_setup() -> None:
    state = _default_state(5)
    assert state.phase is GamePhase.TEAM_PROPOSAL
    assert state.round_number == 1
    assert state.attempt_number == 1
    assert state.current_leader.player_id == state.players[0].player_id
    assert state.resistance_score == 0
    assert state.minion_score == 0


def test_propose_team_happy_path_transitions_to_vote() -> None:
    state = _default_state(5)
    team_size = state.config.mission_config.team_sizes[state.round_number - 1]
    team = _team_members(state, team_size)
    proposal = state.propose_team(state.current_leader.player_id, team)
    assert proposal == team
    assert state.phase is GamePhase.TEAM_VOTE


def test_propose_team_rejects_wrong_leader() -> None:
    state = _default_state(5)
    team_size = state.config.mission_config.team_sizes[state.round_number - 1]
    team = _team_members(state, team_size)
    wrong_leader = state.players[1].player_id
    with pytest.raises(InvalidActionError):
        state.propose_team(wrong_leader, team)


def test_propose_team_rejects_duplicate_players() -> None:
    state = _default_state(5)
    team_size = state.config.mission_config.team_sizes[state.round_number - 1]
    member = state.players[0].player_id
    team = tuple(member for _ in range(team_size))
    with pytest.raises(InvalidActionError):
        state.propose_team(state.current_leader.player_id, team)


def test_propose_team_enforces_team_size() -> None:
    state = _default_state(5)
    team_size = state.config.mission_config.team_sizes[state.round_number - 1]
    too_large_team = _team_members(state, team_size + 1)
    with pytest.raises(InvalidActionError):
        state.propose_team(state.current_leader.player_id, too_large_team)


def test_vote_requires_all_players() -> None:
    state = _default_state(5)
    team_size = state.config.mission_config.team_sizes[state.round_number - 1]
    team = _team_members(state, team_size)
    state.propose_team(state.current_leader.player_id, team)
    votes = {player.player_id: True for player in state.players}
    votes.pop(team[0])
    with pytest.raises(InvalidActionError):
        state.vote_on_team(votes)


def test_vote_rejection_rotates_leader_and_increments_attempt() -> None:
    state = _default_state(5)
    team_size = state.config.mission_config.team_sizes[state.round_number - 1]
    team = _team_members(state, team_size)
    state.propose_team(state.current_leader.player_id, team)
    votes = {player.player_id: False for player in state.players}
    record = state.vote_on_team(votes)
    assert not record.approved
    assert state.phase is GamePhase.TEAM_PROPOSAL
    assert state.attempt_number == 2
    assert state.current_leader.player_id == state.players[1].player_id


def test_vote_approval_moves_to_mission_phase() -> None:
    state = _default_state(5)
    team_size = state.config.mission_config.team_sizes[state.round_number - 1]
    team = _team_members(state, team_size)
    state.propose_team(state.current_leader.player_id, team)
    approvals = {player.player_id: True for player in state.players}
    record = state.vote_on_team(approvals)
    assert record.approved
    assert state.phase is GamePhase.MISSION


def test_auto_fail_after_five_rejections_awards_minion_point() -> None:
    state = _default_state(5)
    record = None
    for _ in range(5):
        team_size = state.config.mission_config.team_sizes[state.round_number - 1]
        team = _team_members(state, team_size)
        state.propose_team(state.current_leader.player_id, team)
        votes = {player.player_id: False for player in state.players}
        record = state.vote_on_team(votes)
    assert record is not None
    assert not record.approved
    assert state.missions
    final_mission = state.missions[-1]
    assert final_mission.auto_fail
    assert final_mission.result is MissionResult.FAILURE
    assert state.minion_score == 1
    assert state.round_number == 2


def test_mission_success_increments_resistance_and_advances_round() -> None:
    state = _default_state(5)
    team_size = state.config.mission_config.team_sizes[state.round_number - 1]
    team = _team_members(state, team_size)
    record = _run_mission(state, team, {pid: MissionDecision.SUCCESS for pid in team})
    assert record.result is MissionResult.SUCCESS
    assert state.resistance_score == 1
    assert state.round_number == 2
    assert state.phase is GamePhase.TEAM_PROPOSAL


def test_mission_failure_increments_minion_score() -> None:
    state = _default_state(5)
    team_size = state.config.mission_config.team_sizes[state.round_number - 1]
    team = _team_with_minion(state, team_size)
    decisions = {pid: MissionDecision.SUCCESS for pid in team}
    failing_minion = next(
        pid for pid in team if state.players_by_id[pid].alignment is Alignment.MINION
    )
    decisions[failing_minion] = MissionDecision.FAIL
    record = _run_mission(state, team, decisions)
    assert record.result is MissionResult.FAILURE
    assert state.minion_score == 1
    assert state.phase is GamePhase.TEAM_PROPOSAL


def test_resistance_reaches_three_successes_moves_to_assassination_when_assassin_present() -> None:
    state = _default_state(7)
    for _ in range(3):
        team_size = state.config.mission_config.team_sizes[state.round_number - 1]
        team = _team_members(state, team_size)
        _run_mission(state, team, {pid: MissionDecision.SUCCESS for pid in team})
    assert state.resistance_score == 3
    assert state.provisional_winner is Alignment.RESISTANCE
    assert state.phase is GamePhase.ASSASSINATION_PENDING
    assert state.final_winner is None


def test_resistance_victory_without_assassin_ends_game() -> None:
    base_config = GameConfig.default(5)
    custom_roles = tuple(
        RoleType.LOYAL_SERVANT
        if role in (RoleType.MERLIN, RoleType.PERCIVAL)
        else RoleType.MINION_OF_MORDRED
        if role is RoleType.ASSASSIN
        else role
        for role in base_config.roles
    )
    config = base_config.with_roles(custom_roles)
    registrations = [PlayerRegistration(f"Player {i}") for i in range(1, config.player_count + 1)]
    setup = perform_setup(config, registrations, seed=13)
    state = GameState.from_setup(setup)
    for _ in range(3):
        team_size = state.config.mission_config.team_sizes[state.round_number - 1]
        team = _team_members(state, team_size)
        _run_mission(state, team, {pid: MissionDecision.SUCCESS for pid in team})
    assert state.resistance_score == 3
    assert state.final_winner is Alignment.RESISTANCE
    assert state.phase is GamePhase.GAME_OVER


def test_mission_four_requires_two_fail_cards() -> None:
    state = _reach_round_four_state()
    team_size = state.config.mission_config.team_sizes[state.round_number - 1]
    team = _team_with_minions(state, team_size, 2)
    decisions = {pid: MissionDecision.SUCCESS for pid in team}
    decisions[team[0]] = MissionDecision.FAIL
    record = _run_mission(state, team, decisions)
    assert record.required_fail_count == 2
    assert record.fail_count == 1
    assert record.result is MissionResult.SUCCESS
    assert state.resistance_score == 3
    assert state.phase is GamePhase.ASSASSINATION_PENDING


def test_two_fail_cards_on_fourth_mission_causes_failure() -> None:
    state = _reach_round_four_state(seed=43)
    team_size = state.config.mission_config.team_sizes[state.round_number - 1]
    team = _team_with_minions(state, team_size, 2)
    decisions = {pid: MissionDecision.SUCCESS for pid in team}
    decisions[team[0]] = MissionDecision.FAIL
    decisions[team[1]] = MissionDecision.FAIL
    record = _run_mission(state, team, decisions)
    assert record.required_fail_count == 2
    assert record.fail_count == 2
    assert record.result is MissionResult.FAILURE
    assert state.minion_score == 2
    assert state.round_number == 5
    assert state.phase is GamePhase.TEAM_PROPOSAL


def test_minions_win_after_three_failed_missions() -> None:
    state = _default_state(5)
    for _ in range(3):
        team_size = state.config.mission_config.team_sizes[state.round_number - 1]
        team = _team_with_minion(state, team_size)
        decisions = {pid: MissionDecision.SUCCESS for pid in team}
        failing_minion = next(
            pid for pid in team if state.players_by_id[pid].alignment is Alignment.MINION
        )
        decisions[failing_minion] = MissionDecision.FAIL
        _run_mission(state, team, decisions)
        if state.phase is GamePhase.GAME_OVER:
            break
    assert state.minion_score == 3
    assert state.final_winner is Alignment.MINION
    assert state.phase is GamePhase.GAME_OVER


def test_resistance_player_cannot_submit_fail_decision() -> None:
    state = _default_state(5)
    team_size = state.config.mission_config.team_sizes[state.round_number - 1]
    team = _team_of_resistance(state, team_size)
    _approve_team(state, team)
    decisions = {pid: MissionDecision.SUCCESS for pid in team}
    decisions[team[0]] = MissionDecision.FAIL
    with pytest.raises(InvalidActionError):
        state.submit_mission(decisions)


def test_invalid_phase_actions_raise_errors() -> None:
    state = _default_state(5)
    with pytest.raises(InvalidActionError):
        state.vote_on_team({player.player_id: True for player in state.players})
    with pytest.raises(InvalidActionError):
        state.submit_mission({})
    team_size = state.config.mission_config.team_sizes[state.round_number - 1]
    team = _team_members(state, team_size)
    state.propose_team(state.current_leader.player_id, team)
    with pytest.raises(InvalidActionError):
        state.submit_mission({pid: MissionDecision.SUCCESS for pid in team})
