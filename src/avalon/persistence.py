"""Serialization helpers for saving and loading Avalon game state."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .config import GameConfig
from .enums import Alignment, RoleType
from .events import EventLog, GameEvent
from .game_state import (
    AssassinationRecord,
    GamePhase,
    GameState,
    MissionAction,
    MissionDecision,
    MissionRecord,
    MissionResult,
    VoteRecord,
)
from .players import Player


@dataclass(frozen=True, slots=True)
class GameStateSnapshot:
    """Structured representation of a :class:`GameState` suitable for persistence."""

    payload: dict[str, Any]

    def to_json(self, *, indent: int = 2) -> str:
        """Serialise the snapshot to JSON."""

        return json.dumps(self.payload, indent=indent)

    def to_dict(self) -> dict[str, Any]:
        """Return a deep copy of the underlying payload."""

        return json.loads(json.dumps(self.payload))

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "GameStateSnapshot":
        """Build a snapshot from raw dictionary data."""

        return cls(payload=dict(data))

    @classmethod
    def from_game_state(cls, state: GameState) -> "GameStateSnapshot":
        """Capture the provided game state as a snapshot."""

        return cls(payload=_state_to_payload(state))

    def restore(self) -> GameState:
        """Rehydrate the snapshot back into a :class:`GameState`."""

        return _payload_to_state(self.payload)

    def save(self, path: str | Path, *, indent: int = 2) -> None:
        """Persist the snapshot to disk as JSON."""

        Path(path).write_text(self.to_json(indent=indent), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "GameStateSnapshot":
        """Load a snapshot from disk."""

        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(data)


def snapshot_game_state(state: GameState) -> GameStateSnapshot:
    """Produce a :class:`GameStateSnapshot` for the supplied state."""

    return GameStateSnapshot.from_game_state(state)


def restore_game_state(snapshot: GameStateSnapshot) -> GameState:
    """Restore a :class:`GameState` instance from ``snapshot``."""

    return snapshot.restore()


def _state_to_payload(state: GameState) -> dict[str, Any]:
    return {
        "config": _config_to_dict(state.config),
        "players": [_player_to_dict(player) for player in state.players],
        "state": {
            "phase": state.phase.value,
            "round_number": state.round_number,
            "attempt_number": state.attempt_number,
            "leader_index": state.leader_index,
            "resistance_score": state.resistance_score,
            "minion_score": state.minion_score,
            "current_team": list(state.current_team) if state.current_team else None,
            "consecutive_rejections": state.consecutive_rejections,
            "provisional_winner": state.provisional_winner.value
            if state.provisional_winner
            else None,
            "final_winner": state.final_winner.value if state.final_winner else None,
        },
        "votes": [_vote_to_dict(record) for record in state.votes],
        "missions": [_mission_to_dict(record) for record in state.missions],
        "assassination": _assassination_to_dict(state.assassination),
        "seed": state.seed,
        "event_log": _event_log_to_list(state.event_log),
    }


def _payload_to_state(payload: Mapping[str, Any]) -> GameState:
    config = _dict_to_config(payload["config"])
    players = tuple(_dict_to_player(raw) for raw in payload["players"])
    state_block = payload["state"]
    phase = GamePhase(state_block["phase"])
    current_team_raw = state_block.get("current_team")
    current_team = tuple(current_team_raw) if current_team_raw else None
    provisional = state_block.get("provisional_winner")
    final = state_block.get("final_winner")

    votes = [_dict_to_vote(raw) for raw in payload.get("votes", [])]
    missions = [_dict_to_mission(raw) for raw in payload.get("missions", [])]
    assassination = _dict_to_assassination(payload.get("assassination"))

    event_log_data = payload.get("event_log") or []
    events = [_dict_to_event(item) for item in event_log_data]
    event_log = EventLog.from_events(events) if events else None

    state = GameState(
        config=config,
        players=players,
        phase=phase,
        round_number=state_block["round_number"],
        attempt_number=state_block["attempt_number"],
        leader_index=state_block["leader_index"],
        resistance_score=state_block["resistance_score"],
        minion_score=state_block["minion_score"],
        current_team=current_team,
        consecutive_rejections=state_block["consecutive_rejections"],
        provisional_winner=Alignment(provisional) if provisional else None,
        final_winner=Alignment(final) if final else None,
        vote_history=votes,
        mission_history=missions,
        seed=payload.get("seed"),
        event_log=event_log,
        assassination_record=assassination,
    )
    return state


def _config_to_dict(config: GameConfig) -> dict[str, Any]:
    return {
        "player_count": config.player_count,
        "roles": [role.value for role in config.roles],
        "lady_of_the_lake_enabled": config.lady_of_the_lake_enabled,
        "random_seed": config.random_seed,
    }


def _dict_to_config(data: Mapping[str, Any]) -> GameConfig:
    roles = tuple(RoleType(role) for role in data["roles"])
    return GameConfig(
        player_count=data["player_count"],
        roles=roles,
        lady_of_the_lake_enabled=data.get("lady_of_the_lake_enabled", False),
        random_seed=data.get("random_seed"),
    )


def _player_to_dict(player: Player) -> dict[str, Any]:
    return {
        "player_id": player.player_id,
        "display_name": player.display_name,
        "role": player.role.value,
        "public_history_ids": list(player.public_history_ids),
        "private_note_keys": list(player.private_note_keys),
    }


def _dict_to_player(data: Mapping[str, Any]) -> Player:
    return Player(
        player_id=data["player_id"],
        display_name=data["display_name"],
        role=RoleType(data["role"]),
        public_history_ids=tuple(data.get("public_history_ids", [])),
        private_note_keys=tuple(data.get("private_note_keys", [])),
    )


def _vote_to_dict(record: VoteRecord) -> dict[str, Any]:
    return {
        "round_number": record.round_number,
        "attempt_number": record.attempt_number,
        "leader_id": record.leader_id,
        "team": list(record.team),
        "approvals": list(record.approvals),
        "rejections": list(record.rejections),
        "approved": record.approved,
    }


def _dict_to_vote(data: Mapping[str, Any]) -> VoteRecord:
    return VoteRecord(
        round_number=data["round_number"],
        attempt_number=data["attempt_number"],
        leader_id=data["leader_id"],
        team=tuple(data["team"]),
        approvals=tuple(data["approvals"]),
        rejections=tuple(data["rejections"]),
        approved=data["approved"],
    )


def _mission_to_dict(record: MissionRecord) -> dict[str, Any]:
    return {
        "round_number": record.round_number,
        "attempt_number": record.attempt_number,
        "team": list(record.team),
        "fail_count": record.fail_count,
        "required_fail_count": record.required_fail_count,
        "result": record.result.value,
        "auto_fail": record.auto_fail,
        "actions": [
            {"player_id": action.player_id, "decision": action.decision.value}
            for action in record.actions
        ],
    }


def _dict_to_mission(data: Mapping[str, Any]) -> MissionRecord:
    actions = tuple(
        MissionAction(player_id=item["player_id"], decision=MissionDecision(item["decision"]))
        for item in data.get("actions", [])
    )
    return MissionRecord(
        round_number=data["round_number"],
        attempt_number=data["attempt_number"],
        team=tuple(data["team"]),
        fail_count=data["fail_count"],
        required_fail_count=data["required_fail_count"],
        result=MissionResult(data["result"]),
        auto_fail=data.get("auto_fail", False),
        actions=actions,
    )


def _assassination_to_dict(record: AssassinationRecord | None) -> dict[str, Any] | None:
    if record is None:
        return None
    return {
        "assassin_id": record.assassin_id,
        "target_id": record.target_id,
        "success": record.success,
    }


def _dict_to_assassination(data: Mapping[str, Any] | None) -> AssassinationRecord | None:
    if not data:
        return None
    return AssassinationRecord(
        assassin_id=data["assassin_id"],
        target_id=data["target_id"],
        success=data["success"],
    )


def _event_log_to_list(log: EventLog | None) -> list[dict[str, Any]]:
    if log is None:
        return []
    return [event.to_dict() for event in log.events]


def _dict_to_event(data: Mapping[str, Any]) -> GameEvent:
    # ``GameEventType`` import kept for completeness; construction happens via :meth:`from_dict`.
    return GameEvent.from_dict(data)


__all__ = [
    "GameStateSnapshot",
    "restore_game_state",
    "snapshot_game_state",
]
