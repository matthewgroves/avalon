"""Enhanced logging for agent decisions and game analysis."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .agents import (
        AgentObservation,
        AssassinationGuess,
        MissionAction,
        TeamProposal,
        VoteDecision,
    )
    from .players import PlayerId


class LoggingManager:
    """Manages detailed logging of agent decisions for debugging and analysis."""

    def __init__(self, enabled: bool = False, base_dir: Path | None = None) -> None:
        """Initialize the logging manager.

        Args:
            enabled: Whether enhanced logging is enabled
            base_dir: Base directory for logs (defaults to ./logs)
        """
        self.enabled = enabled
        if not enabled:
            return

        # Create timestamped log directory
        if base_dir is None:
            base_dir = Path("logs")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_dir = base_dir / timestamp
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Track log files per player
        self.player_files: dict[PlayerId, Path] = {}

    def _get_log_file(self, player_id: PlayerId) -> Path:
        """Get or create the log file path for a player."""
        if player_id not in self.player_files:
            filename = f"player_{player_id}.log"
            self.player_files[player_id] = self.log_dir / filename
        return self.player_files[player_id]

    def _write_log(self, player_id: PlayerId, content: str) -> None:
        """Write content to a player's log file."""
        if not self.enabled:
            return

        log_file = self._get_log_file(player_id)
        with open(log_file, "a") as f:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"\n{'=' * 80}\n")
            f.write(f"[{timestamp}]\n")
            f.write(content)
            f.write("\n")

    def log_team_proposal(
        self,
        player_id: PlayerId,
        observation: AgentObservation,
        decision: TeamProposal,
    ) -> None:
        """Log a team proposal decision."""
        if not self.enabled:
            return

        content = f"""TEAM PROPOSAL DECISION

OBSERVATION:
{self._format_observation(observation)}

DECISION:
  Proposed Team: {decision.team}
  True Reasoning: {decision.true_reasoning}
  Public Reasoning: {decision.public_reasoning}
"""
        self._write_log(player_id, content)

    def log_team_vote(
        self,
        player_id: PlayerId,
        observation: AgentObservation,
        decision: VoteDecision,
    ) -> None:
        """Log a team vote decision."""
        if not self.enabled:
            return

        content = f"""TEAM VOTE DECISION

OBSERVATION:
{self._format_observation(observation)}

DECISION:
  Vote: {decision.approve}
  True Reasoning: {decision.true_reasoning}
  Public Reasoning: {decision.public_reasoning}
"""
        self._write_log(player_id, content)

    def log_mission_action(
        self,
        player_id: PlayerId,
        observation: AgentObservation,
        decision: MissionAction,
    ) -> None:
        """Log a mission action decision."""
        if not self.enabled:
            return

        content = f"""MISSION ACTION DECISION

OBSERVATION:
{self._format_observation(observation)}

DECISION:
  Action: {decision.success}
  True Reasoning: {decision.true_reasoning}
  Public Reasoning: {decision.public_reasoning}
"""
        self._write_log(player_id, content)

    def log_assassination(
        self,
        player_id: PlayerId,
        observation: AgentObservation,
        decision: AssassinationGuess,
    ) -> None:
        """Log an assassination decision."""
        if not self.enabled:
            return

        content = f"""ASSASSINATION DECISION

OBSERVATION:
{self._format_observation(observation)}

DECISION:
  Target: {decision.target_id}
  True Reasoning: {decision.true_reasoning}
  Public Reasoning: {decision.public_reasoning}
"""
        self._write_log(player_id, content)

    def _format_observation(self, obs: AgentObservation) -> str:
        """Format an observation for logging."""
        lines = []
        lines.append(f"  Player ID: {obs.player_id}")
        lines.append(f"  Display Name: {obs.display_name}")
        lines.append(f"  Role: {obs.role}")
        lines.append(f"  Alignment: {obs.alignment}")
        lines.append(f"  Knowledge: {obs.knowledge}")
        lines.append(f"  Phase: {obs.phase}")
        lines.append(f"  Round: {obs.round_number}")
        lines.append(f"  Attempt: {obs.attempt_number}")
        lines.append(f"  Score - Resistance: {obs.resistance_score}, Minions: {obs.minion_score}")
        lines.append(f"  Consecutive Rejections: {obs.consecutive_rejections}")
        lines.append(f"  Current Leader: {obs.current_leader_id}")
        lines.append(f"  Mission History: {obs.mission_history}")
        lines.append(f"  Current Team: {obs.current_team}")
        lines.append(f"  Vote History: {obs.vote_history}")
        lines.append(f"  Required Team Size: {obs.required_team_size}")
        lines.append(f"  Required Fail Count: {obs.required_fail_count}")

        if obs.public_statements:
            lines.append("  Recent Public Statements:")
            for player, decision_type, statement in obs.public_statements:
                lines.append(f"    - Player {player} ({decision_type}): {statement}")

        return "\n".join(lines)
