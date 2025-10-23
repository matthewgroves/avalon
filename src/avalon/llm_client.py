"""LLM client for agent decision-making using Google's Gemini API."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Protocol

import google.generativeai as genai

from .agents import (
    AgentObservation,
    AssassinationGuess,
    MissionAction,
    TeamProposal,
    VoteDecision,
)
from .exceptions import ConfigurationError


class LLMClient(Protocol):
    """Protocol for LLM clients that generate agent decisions."""

    def propose_team(self, observation: AgentObservation) -> TeamProposal:
        """Generate a team proposal based on game observation."""
        ...

    def vote_on_team(self, observation: AgentObservation) -> VoteDecision:
        """Generate a vote decision based on game observation."""
        ...

    def execute_mission(self, observation: AgentObservation) -> MissionAction:
        """Generate a mission action based on game observation."""
        ...

    def guess_merlin(self, observation: AgentObservation) -> AssassinationGuess:
        """Generate an assassination guess based on game observation."""
        ...


@dataclass
class GeminiClient:
    """Google Gemini API client for agent decision-making.

    Uses Gemini 2.0 Flash model for fast, cost-effective gameplay.
    Requires GEMINI_API_KEY environment variable.
    """

    model_name: str = "gemini-2.0-flash-exp"
    temperature: float = 0.7
    api_key: str | None = None

    def __post_init__(self) -> None:
        """Configure API client."""
        if self.api_key is None:
            self.api_key = os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ConfigurationError(
                "GEMINI_API_KEY environment variable is required for agent players. "
                "Get your API key from https://aistudio.google.com/apikey"
            )
        genai.configure(api_key=self.api_key)
        self._model = genai.GenerativeModel(self.model_name)

    def _generate_text(self, prompt: str) -> str:
        """Generate text completion from prompt."""
        response = self._model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=self.temperature,
                max_output_tokens=1000,
            ),
        )
        return response.text

    def _build_game_context(self) -> str:
        """Build general game context and strategic guidance."""
        return """You are playing The Resistance: Avalon, a social deduction game of \
hidden roles and imperfect information.

GAME OVERVIEW:
- Two teams compete: Resistance (good) vs Minions of Mordred (evil)
- Resistance wins by passing 3 missions; Minions win by failing 3 missions
- Special roles have partial knowledge (e.g., Merlin knows evil players)
- The game thrives on deception, deduction, and strategic discussion

KEY STRATEGIES:
- Disguise your role: Don't reveal your alignment through obvious patterns
- Use imperfect information: Make decisions that could be justified by multiple roles
- Consider table dynamics: Who is pushing certain narratives? Why?
- Resistance: Build trust carefully, observe who sabotages missions
- Minions: Blend in, create doubt, subtly guide missions toward failure
- Special roles: Use your knowledge wisely without exposing yourself"""

    def _build_observation_context(self, observation: AgentObservation) -> str:
        """Build a text description of the game state for the agent."""
        lines = [
            f"You are {observation.display_name} ({observation.player_id})",
            f"Role: {observation.role.value.replace('_', ' ').title()}",
            f"Alignment: {observation.alignment.value.title()}",
            "",
            "Game State:",
            f"- Phase: {observation.phase.value}",
            f"- Round: {observation.round_number}, Attempt: {observation.attempt_number}",
            f"- Score: Resistance {observation.resistance_score} - "
            f"{observation.minion_score} Minions",
            f"- Consecutive rejections: {observation.consecutive_rejections}",
            "",
            "Players:",
        ]

        # List all players
        for player_id, name in zip(
            observation.all_player_ids, observation.all_player_names, strict=True
        ):
            leader_mark = " (LEADER)" if player_id == observation.current_leader_id else ""
            lines.append(f"  - {player_id}: {name}{leader_mark}")

        # Role knowledge
        if observation.knowledge.has_information:
            lines.append("")
            lines.append("Your role knowledge:")
            if observation.knowledge.visible_player_ids:
                visible_names = [
                    observation.all_player_names[observation.all_player_ids.index(pid)]
                    for pid in observation.knowledge.visible_player_ids
                ]
                lines.append(f"  - You know these players: {', '.join(visible_names)}")
            if observation.knowledge.ambiguous_player_id_groups:
                for group in observation.knowledge.ambiguous_player_id_groups:
                    group_names = [
                        observation.all_player_names[observation.all_player_ids.index(pid)]
                        for pid in group
                    ]
                    lines.append(f"  - Ambiguous group: {', '.join(group_names)}")

        # Current team if proposed
        if observation.current_team:
            lines.append("")
            team_names = [
                observation.all_player_names[observation.all_player_ids.index(pid)]
                for pid in observation.current_team
            ]
            lines.append(f"Proposed team: {', '.join(team_names)}")

        # Vote history
        if observation.vote_history:
            lines.append("")
            lines.append("Vote history:")
            for vote in observation.vote_history[-3:]:  # Last 3 votes
                lines.append(
                    f"  - Round {vote.round_number}.{vote.attempt_number}: "
                    f"{'APPROVED' if vote.approved else 'REJECTED'} "
                    f"({len(vote.approvals)} approve, {len(vote.rejections)} reject)"
                )

        # Mission history
        if observation.mission_history:
            lines.append("")
            lines.append("Mission history:")
            for mission in observation.mission_history:
                lines.append(
                    f"  - Round {mission.round_number}: {mission.result.value.upper()} "
                    f"({mission.fail_count} fails)"
                )

        return "\n".join(lines)

    def propose_team(self, observation: AgentObservation) -> TeamProposal:
        """Generate a team proposal using Gemini."""
        game_context = self._build_game_context()
        observation_context = self._build_observation_context(observation)
        prompt = f"""{game_context}

{observation_context}

DECISION: TEAM PROPOSAL
You are the mission leader. You must propose a team of exactly \
{observation.required_team_size} players.

Consider:
- Your alignment: Do you want this mission to succeed or fail?
- Your knowledge: What do you know about other players?
- Deception: How can you justify this team regardless of your true role?
- Table dynamics: Who has been trusted/suspected so far?

Respond with a JSON object in this format:
{{
  "team": ["player_1", "player_2"],
  "reasoning": "brief explanation of your choice"
}}

Your response:"""

        response_text = self._generate_text(prompt)
        parsed = self._parse_json_response(response_text)

        team = tuple(parsed.get("team", []))
        reasoning = parsed.get("reasoning", "")

        # Validate team size
        if len(team) != observation.required_team_size:
            # Fallback: take first N players if invalid
            team = observation.all_player_ids[: observation.required_team_size]
            reasoning = f"Invalid team size, using fallback. Original: {reasoning}"

        return TeamProposal(team=team, reasoning=reasoning)

    def vote_on_team(self, observation: AgentObservation) -> VoteDecision:
        """Generate a vote decision using Gemini."""
        game_context = self._build_game_context()
        observation_context = self._build_observation_context(observation)
        prompt = f"""{game_context}

{observation_context}

DECISION: TEAM VOTE
You must vote to APPROVE or REJECT the proposed team.

Consider:
- Your alignment: Does this team help or hurt your side?
- Your knowledge: Do you recognize any evil/good players on the team?
- Strategic voting: Sometimes voting against your interest can provide cover
- Rejection consequences: {5 - observation.consecutive_rejections} more rejections \
= automatic mission failure
- Patterns: Avoid voting in ways that obviously reveal your role

Respond with a JSON object in this format:
{{
  "approve": true,
  "reasoning": "brief explanation of your vote"
}}

Your response:"""

        response_text = self._generate_text(prompt)
        parsed = self._parse_json_response(response_text)

        approve = parsed.get("approve", False)
        reasoning = parsed.get("reasoning", "")

        return VoteDecision(approve=approve, reasoning=reasoning)

    def execute_mission(self, observation: AgentObservation) -> MissionAction:
        """Generate a mission action using Gemini."""
        game_context = self._build_game_context()
        observation_context = self._build_observation_context(observation)
        prompt = f"""{game_context}

{observation_context}

DECISION: MISSION EXECUTION
You are on the mission team. You must play a SUCCESS or FAIL card.

CRITICAL RULES:
- Resistance players MUST play SUCCESS (you have no choice)
- Minions CAN play SUCCESS or FAIL (your choice is strategic)

Consider (if you're a Minion):
- Suspicion management: Failing too early might expose you
- Mission criticality: Is this a crucial mission to fail?
- Team composition: Are there other minions who might fail?
- Cover strategy: Sometimes playing success builds trust for later betrayal

Respond with a JSON object in this format:
{{
  "success": true,
  "reasoning": "brief explanation of your choice"
}}

Your response:"""

        response_text = self._generate_text(prompt)
        parsed = self._parse_json_response(response_text)

        success = parsed.get("success", True)
        reasoning = parsed.get("reasoning", "")

        # Force resistance to play success
        from .enums import Alignment

        if observation.alignment == Alignment.RESISTANCE:
            success = True
            if not parsed.get("success", True):
                reasoning += " [Forced to SUCCESS - Resistance player]"

        return MissionAction(success=success, reasoning=reasoning)

    def guess_merlin(self, observation: AgentObservation) -> AssassinationGuess:
        """Generate an assassination guess using Gemini."""
        game_context = self._build_game_context()
        observation_context = self._build_observation_context(observation)
        prompt = f"""{game_context}

{observation_context}

DECISION: ASSASSINATE MERLIN
As the Assassin, you must identify and kill Merlin to steal victory from the Resistance.

MERLIN'S CHARACTERISTICS:
- Merlin is a Resistance player who knew the Minions at game start
- Merlin tries to guide missions toward success WITHOUT revealing their knowledge
- Look for players who subtly steered away from evil players
- Look for players who voted wisely but didn't explain how they "knew"

ANALYSIS APPROACH:
- Review mission history: Who was on successful teams?
- Review vote patterns: Who consistently opposed teams with minions?
- Consider knowledge: Who acted like they had information?
- Avoid obvious targets: Sometimes the loudest "leader" isn't Merlin
- Look for subtle guidance: Merlin must hide while helping

Respond with a JSON object in this format:
{{
  "target_id": "player_3",
  "reasoning": "brief explanation of your guess"
}}

Your response:"""

        response_text = self._generate_text(prompt)
        parsed = self._parse_json_response(response_text)

        target_id = parsed.get("target_id", observation.all_player_ids[0])
        reasoning = parsed.get("reasoning", "")

        # Validate target exists
        if target_id not in observation.all_player_ids:
            target_id = observation.all_player_ids[0]
            reasoning = f"Invalid target, using fallback. Original: {reasoning}"

        return AssassinationGuess(target_id=target_id, reasoning=reasoning)

    def _parse_json_response(self, response_text: str) -> dict[str, Any]:
        """Parse JSON from LLM response, handling markdown code blocks."""
        # Try to extract JSON from markdown code blocks
        text = response_text.strip()

        # Remove markdown code block markers if present
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first line (```json or ```)
            lines = lines[1:]
            # Remove last line if it's ```
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Return empty dict as fallback
            return {}


__all__ = ["GeminiClient", "LLMClient"]
