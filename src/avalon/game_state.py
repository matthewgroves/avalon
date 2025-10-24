"""Turn and mission management for Avalon games."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from .config import GameConfig
from .enums import Alignment
from .events import EventLog, GameEventType
from .exceptions import ConfigurationError, InvalidActionError
from .players import Player, PlayerId
from .roles import ROLE_DEFINITIONS, RoleTag
from .setup import SetupResult


class GamePhase(str, Enum):
    """High-level phase of the game loop."""

    TEAM_PROPOSAL = "team_proposal"
    TEAM_VOTE = "team_vote"
    MISSION = "mission"
    ASSASSINATION_PENDING = "assassination_pending"
    GAME_OVER = "game_over"


class MissionResult(str, Enum):
    """Outcome of a mission."""

    SUCCESS = "success"
    FAILURE = "failure"


class MissionDecision(str, Enum):
    """Card submitted during a mission."""

    SUCCESS = "success"
    FAIL = "fail"


@dataclass(frozen=True, slots=True)
class VoteRecord:
    """Record of a team vote."""

    round_number: int
    attempt_number: int
    leader_id: PlayerId
    team: Tuple[PlayerId, ...]
    approvals: Tuple[PlayerId, ...]
    rejections: Tuple[PlayerId, ...]
    approved: bool


@dataclass(frozen=True, slots=True)
class MissionAction:
    """Private record tying a mission card to the submitting player."""

    player_id: PlayerId
    decision: MissionDecision


@dataclass(frozen=True, slots=True)
class MissionSummary:
    """Public mission data safe to expose to players and observers."""

    round_number: int
    attempt_number: int
    team: Tuple[PlayerId, ...]
    fail_count: int
    required_fail_count: int
    result: MissionResult
    auto_fail: bool


@dataclass(frozen=True, slots=True)
class MissionRecord:
    """Aggregated record for a completed mission attempt."""

    round_number: int
    attempt_number: int
    team: Tuple[PlayerId, ...]
    fail_count: int
    required_fail_count: int
    result: MissionResult
    auto_fail: bool = False
    actions: Tuple[MissionAction, ...] = ()

    def to_public_summary(self) -> MissionSummary:
        """Return an aggregated mission view without private card data."""

        return MissionSummary(
            round_number=self.round_number,
            attempt_number=self.attempt_number,
            team=self.team,
            fail_count=self.fail_count,
            required_fail_count=self.required_fail_count,
            result=self.result,
            auto_fail=self.auto_fail,
        )


@dataclass(frozen=True, slots=True)
class AssassinationRecord:
    """Record capturing the outcome of the assassin's guess."""

    assassin_id: PlayerId
    target_id: PlayerId
    success: bool


@dataclass(slots=True)
class GameState:
    """Mutable representation of an in-progress Avalon game."""

    config: GameConfig
    players: Tuple[Player, ...]
    phase: GamePhase = GamePhase.TEAM_PROPOSAL
    round_number: int = 1
    attempt_number: int = 1
    leader_index: int = 0
    resistance_score: int = 0
    minion_score: int = 0
    current_team: Optional[Tuple[PlayerId, ...]] = None
    consecutive_rejections: int = 0
    provisional_winner: Optional[Alignment] = None
    final_winner: Optional[Alignment] = None
    vote_history: list[VoteRecord] = field(default_factory=list, repr=False)
    mission_history: list[MissionRecord] = field(default_factory=list, repr=False)
    seed: Optional[int] = None
    event_log: Optional[EventLog] = field(default=None, repr=False)
    _players_by_id: Dict[PlayerId, Player] = field(init=False, repr=False, default_factory=dict)
    _assassin_present: bool = field(init=False, repr=False, default=False)
    _assassin_ids: Tuple[PlayerId, ...] = field(init=False, repr=False, default=())
    assassination_record: Optional[AssassinationRecord] = None

    def __post_init__(self) -> None:
        player_map = {player.player_id: player for player in self.players}
        if len(player_map) != len(self.players):
            raise ConfigurationError("Duplicate player identifiers detected in game state")
        if self.config.player_count != len(self.players):
            raise ConfigurationError("Player roster does not match configuration count")
        object.__setattr__(self, "_players_by_id", player_map)
        assassin_ids = tuple(
            player.player_id
            for player in self.players
            if RoleTag.ASSASSIN in ROLE_DEFINITIONS[player.role].tags
        )
        has_assassin = bool(assassin_ids)
        object.__setattr__(self, "_assassin_present", has_assassin)
        object.__setattr__(self, "_assassin_ids", assassin_ids)

    @classmethod
    def from_setup(cls, setup: SetupResult) -> "GameState":
        """Create an initial game state from the setup result."""

        return cls(config=setup.config, players=setup.players, seed=setup.seed)

    @property
    def players_by_id(self) -> Mapping[PlayerId, Player]:
        """Return mapping from player identifier to player object."""

        return dict(self._players_by_id)

    @property
    def current_leader(self) -> Player:
        """Return the active leader for the current proposal."""

        return self.players[self.leader_index]

    @property
    def votes(self) -> Tuple[VoteRecord, ...]:
        """Return an immutable snapshot of all recorded votes."""

        return tuple(self.vote_history)

    @property
    def missions(self) -> Tuple[MissionRecord, ...]:
        """Return an immutable snapshot of completed missions."""

        return tuple(self.mission_history)

    @property
    def public_missions(self) -> Tuple[MissionSummary, ...]:
        """Return sanitized mission summaries for public consumption."""

        return tuple(record.to_public_summary() for record in self.mission_history)

    @property
    def assassin_ids(self) -> Tuple[PlayerId, ...]:
        """Return the identifiers of assassin-aligned players."""

        return self._assassin_ids

    @property
    def assassination(self) -> Optional[AssassinationRecord]:
        """Return the resolved assassination record, if any."""

        return self.assassination_record

    def _record_event(
        self,
        event_type: GameEventType,
        payload: Mapping[str, Any] | None = None,
    ) -> None:
        if self.event_log is None:
            return
        self.event_log.record(event_type, payload or {})

    def _set_phase(self, phase: GamePhase) -> None:
        self.phase = phase
        self._record_event(GameEventType.PHASE_CHANGED, {"phase": phase.value})

    def propose_team(self, leader_id: PlayerId, team: Sequence[PlayerId]) -> Tuple[PlayerId, ...]:
        """Propose a mission team for the current round."""

        self._ensure_phase(GamePhase.TEAM_PROPOSAL)
        if leader_id != self.current_leader.player_id:
            raise InvalidActionError("Only the current leader may propose a team")

        team_tuple = tuple(team)
        required_size = self._required_team_size()
        if len(team_tuple) != required_size:
            raise InvalidActionError(
                f"Team size must be {required_size} for round {self.round_number}"
            )
        if len(set(team_tuple)) != len(team_tuple):
            raise InvalidActionError("Team proposals may not contain duplicate players")
        for player_id in team_tuple:
            if player_id not in self._players_by_id:
                raise InvalidActionError(f"Unknown player id in team proposal: {player_id}")

        self.current_team = team_tuple
        self._set_phase(GamePhase.TEAM_VOTE)
        self._record_event(
            GameEventType.TEAM_PROPOSED,
            {
                "round": self.round_number,
                "attempt": self.attempt_number,
                "leader_id": leader_id,
                "team": list(team_tuple),
            },
        )
        return team_tuple

    def vote_on_team(self, votes: Mapping[PlayerId, bool]) -> VoteRecord:
        """Record the simultaneous vote for the currently proposed team."""

        self._ensure_phase(GamePhase.TEAM_VOTE)
        if self.current_team is None:
            raise InvalidActionError("No team has been proposed for voting")
        if set(votes.keys()) != set(self._players_by_id.keys()):
            raise InvalidActionError("Votes must be provided for every registered player")

        approvals = []
        rejections = []
        for player in self.players:
            vote = votes.get(player.player_id)
            if vote not in (True, False):
                raise InvalidActionError("Votes must be boolean values")
            if vote:
                approvals.append(player.player_id)
            else:
                rejections.append(player.player_id)

        approved = len(approvals) > len(rejections)
        record = VoteRecord(
            round_number=self.round_number,
            attempt_number=self.attempt_number,
            leader_id=self.current_leader.player_id,
            team=self.current_team,
            approvals=tuple(approvals),
            rejections=tuple(rejections),
            approved=approved,
        )
        self.vote_history.append(record)
        self._record_event(
            GameEventType.TEAM_VOTE_RECORDED,
            {
                "round": record.round_number,
                "attempt": record.attempt_number,
                "team": list(record.team),
                "approvals": list(record.approvals),
                "rejections": list(record.rejections),
                "approved": record.approved,
            },
        )

        if approved:
            self._set_phase(GamePhase.MISSION)
            self.consecutive_rejections = 0
        else:
            self.consecutive_rejections += 1
            self._advance_leader()
            if self.consecutive_rejections >= 5:
                self._handle_auto_fail()
            else:
                self.attempt_number += 1
                self.current_team = None
                self._set_phase(GamePhase.TEAM_PROPOSAL)

        return record

    def submit_mission(self, decisions: Mapping[PlayerId, MissionDecision]) -> MissionRecord:
        """Submit mission cards for the currently approved team."""

        self._ensure_phase(GamePhase.MISSION)
        if self.current_team is None:
            raise InvalidActionError("No team has been approved for the mission")
        if set(decisions.keys()) != set(self.current_team):
            raise InvalidActionError("Mission decisions must be submitted by the mission team only")

        fail_count = 0
        actions = []
        for player_id in self.current_team:
            decision = decisions[player_id]
            player = self._players_by_id[player_id]
            if decision not in (MissionDecision.SUCCESS, MissionDecision.FAIL):
                raise InvalidActionError("Mission decisions must be SUCCESS or FAIL")
            if player.alignment is Alignment.RESISTANCE and decision is MissionDecision.FAIL:
                raise InvalidActionError("Resistance players may not fail missions")
            if decision is MissionDecision.FAIL:
                fail_count += 1
            actions.append(MissionAction(player_id=player_id, decision=decision))

        required_fails = self._required_fail_count()
        mission_success = fail_count < required_fails
        result = MissionResult.SUCCESS if mission_success else MissionResult.FAILURE
        obfuscated_actions = self._obfuscate_actions(
            actions,
            round_number=self.round_number,
            attempt_number=self.attempt_number,
        )
        record = MissionRecord(
            round_number=self.round_number,
            attempt_number=self.attempt_number,
            team=self.current_team,
            fail_count=fail_count,
            required_fail_count=required_fails,
            result=result,
            actions=obfuscated_actions,
        )
        self.mission_history.append(record)
        self.current_team = None
        self._record_event(
            GameEventType.MISSION_RESOLVED,
            {
                "round": record.round_number,
                "attempt": record.attempt_number,
                "team": list(record.team),
                "fail_count": record.fail_count,
                "required_fail_count": record.required_fail_count,
                "result": record.result.value,
                "auto_fail": record.auto_fail,
            },
        )

        if mission_success:
            self._handle_resistance_success()
        else:
            self._handle_minion_success()

        return record

    def perform_assassination(
        self,
        assassin_id: PlayerId,
        target_id: PlayerId,
    ) -> AssassinationRecord:
        """Resolve the Merlin assassination attempt."""

        if self.phase is not GamePhase.ASSASSINATION_PENDING:
            raise InvalidActionError("Assassination is not currently available")
        if self.assassination_record is not None or self.final_winner is not None:
            raise InvalidActionError("Assassination has already been resolved")
        if assassin_id not in self._assassin_ids:
            raise InvalidActionError("Only the assassin may perform the assassination")
        if target_id not in self._players_by_id:
            raise InvalidActionError("Unknown assassination target")

        target = self._players_by_id[target_id]
        success = RoleTag.MERLIN in ROLE_DEFINITIONS[target.role].tags
        self.final_winner = Alignment.MINION if success else Alignment.RESISTANCE
        self.provisional_winner = self.final_winner
        self._set_phase(GamePhase.GAME_OVER)
        record = AssassinationRecord(assassin_id=assassin_id, target_id=target_id, success=success)
        self.assassination_record = record
        self._record_event(
            GameEventType.ASSASSINATION_RESOLVED,
            {
                "assassin_id": assassin_id,
                "target_id": target_id,
                "success": success,
            },
        )
        self._record_event(
            GameEventType.GAME_COMPLETED,
            {
                "winner": self.final_winner.value,
                "reason": "assassination_success" if success else "assassination_failure",
            },
        )
        return record

    def _handle_resistance_success(self) -> None:
        self.resistance_score += 1
        if self.resistance_score >= 3:
            self.provisional_winner = Alignment.RESISTANCE
            if self._assassin_present:
                self._set_phase(GamePhase.ASSASSINATION_PENDING)
            else:
                self.final_winner = Alignment.RESISTANCE
                self._set_phase(GamePhase.GAME_OVER)
                self._record_event(
                    GameEventType.GAME_COMPLETED,
                    {"winner": Alignment.RESISTANCE.value, "reason": "three_successful_missions"},
                )
            return

        self._advance_leader()
        self._prepare_next_round()

    def _handle_minion_success(self) -> None:
        self.minion_score += 1
        if self.minion_score >= 3:
            self.final_winner = Alignment.MINION
            self._set_phase(GamePhase.GAME_OVER)
            self._record_event(
                GameEventType.GAME_COMPLETED,
                {"winner": Alignment.MINION.value, "reason": "three_failed_missions"},
            )
            return

        self._advance_leader()
        self._prepare_next_round()

    def _handle_auto_fail(self) -> None:
        """Handle 5 consecutive rejections - this ends the game immediately with evil victory."""
        required_fails = self._required_fail_count()
        record = MissionRecord(
            round_number=self.round_number,
            attempt_number=self.attempt_number,
            team=(),
            fail_count=0,
            required_fail_count=required_fails,
            result=MissionResult.FAILURE,
            auto_fail=True,
            actions=(),
        )
        self.mission_history.append(record)
        self.current_team = None

        # 5 consecutive rejections = immediate game over, evil wins
        self.final_winner = Alignment.MINION
        self._set_phase(GamePhase.GAME_OVER)
        self._record_event(
            GameEventType.MISSION_AUTO_FAILED,
            {
                "round": record.round_number,
                "attempt": record.attempt_number,
                "required_fail_count": record.required_fail_count,
            },
        )
        self._record_event(
            GameEventType.GAME_COMPLETED,
            {"winner": Alignment.MINION.value, "reason": "five_consecutive_rejections"},
        )

    def _prepare_next_round(self) -> None:
        if self.round_number >= len(self.config.mission_config.team_sizes):
            self._set_phase(GamePhase.GAME_OVER)
            return

        self.round_number += 1
        self.attempt_number = 1
        self._set_phase(GamePhase.TEAM_PROPOSAL)
        self.consecutive_rejections = 0

    def _advance_leader(self) -> None:
        self.leader_index = (self.leader_index + 1) % len(self.players)

    def _required_team_size(self) -> int:
        return self.config.mission_config.team_sizes[self.round_number - 1]

    def _required_fail_count(self) -> int:
        return self.config.mission_config.required_fail_counts[self.round_number - 1]

    def _ensure_phase(self, expected: GamePhase) -> None:
        if self.phase is GamePhase.GAME_OVER:
            raise InvalidActionError("Game is already over")
        if self.phase is not expected:
            raise InvalidActionError(
                f"Action requires phase {expected.value}, current phase is {self.phase.value}"
            )

    def _obfuscate_actions(
        self,
        actions: Sequence[MissionAction],
        *,
        round_number: int,
        attempt_number: int,
    ) -> Tuple[MissionAction, ...]:
        obfuscated = list(actions)
        base_seed = self.seed if self.seed is not None else 0
        combined_seed = (base_seed << 32) ^ (round_number << 8) ^ attempt_number
        random.Random(combined_seed).shuffle(obfuscated)
        return tuple(obfuscated)
