"""LLM client for agent decision-making using Google's Gemini API."""

from __future__ import annotations

import json
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Protocol

import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

from .agents import (
    AgentObservation,
    AssassinationGuess,
    DiscussionResponse,
    MissionAction,
    TeamProposal,
    VoteDecision,
)
from .discussion import DiscussionPhase
from .enums import Alignment, RoleType
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

    def make_statement(self, observation: AgentObservation, phase: str) -> DiscussionResponse:
        """Generate a discussion statement based on game observation."""
        ...


class BaseLLMClient(ABC):
    """Base class with shared prompt building and decision-making logic.

    Subclasses must implement:
    - __post_init__(): Initialize the API client
    - _generate_text(prompt: str) -> str: Generate text from prompt

    Subclasses should define these attributes:
    - temperature: float
    - max_retries: int
    - base_retry_delay: float
    """

    @abstractmethod
    def _generate_text(self, prompt: str) -> str:
        """Generate text from prompt. Must be implemented by subclasses."""
        ...

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
- Special roles: Use your knowledge wisely without exposing yourself

CRITICAL ANALYTICAL SKILLS:
- Mission Pattern Analysis: Players appearing on MULTIPLE failed missions are HIGHLY suspicious
  * If same players are on 2+ failed missions, they likely contain evil
  * Cross-reference mission teams with your role knowledge
- Vote Pattern Analysis: Who approves/rejects which teams reveals alignment
  * Evil players often approve teams with other evil players
  * Resistance players should be wary of repeatedly approved failing teams
- Information Forcing: Rejecting teams strategically gains information
  * Forcing new proposals reveals who else people trust
  * WARNING: 5 consecutive rejections = INSTANT GAME OVER (evil wins immediately!)
  * Resistance must be EXTREMELY careful about approaching 5 rejections
  * Evil can use rejection pressure as their ultimate weapon
- Logical Consistency: Track what players claim vs. what actually happened
  * If someone says "everyone played success" but mission failed - they're lying or confused
  * Players who misrepresent facts may be covering for evil

AUTO-FAIL MECHANIC (GAME-ENDING):
- If 5 team proposals are rejected in a row, THE GAME ENDS IMMEDIATELY - EVIL WINS
- This is NOT just a failed mission - it's an INSTANT VICTORY for evil
- Resistance perspective: 
  * Use rejections 1-4 strategically (force better teams, gather information)
  * The 5th attempt is CRITICAL - everyone must approve or lose instantly
  * In practice, auto-fail rarely happens because resistance approves on 5th
- Evil perspective: The REAL goal is getting evil ON the 5th team, not rejecting it
  * Why? Because resistance (majority) will all approve the 5th team
  * If evil rejects 5th team, they reveal themselves AND the team passes anyway
  * Smart evil strategy: Use rejections 1-4 to force a 5th team WITH evil players
- At 4 rejections (5th attempt): Resistance MUST approve, Evil SHOULD approve (to blend in)

AVOID THESE COMMON MISTAKES:
- Don't claim "team size" is strategic - it's determined by game rules (round number + player count)
- Don't say "gather information" without USING the information you've gathered
- Don't approve the same suspicious players repeatedly without strong justification
- Don't contradict observable facts (e.g., mission results, who was on teams)
- DON'T reject on the 5th attempt if you're Resistance (you lose the ENTIRE GAME)
- DON'T propose the exact same team that was just rejected"""

    def _build_role_guidance(self, observation: AgentObservation) -> str:
        """Build role-specific strategic guidance."""
        from .enums import RoleType

        role = observation.role
        guidance_lines = ["\nYOUR ROLE-SPECIFIC GUIDANCE:"]

        if role == RoleType.MERLIN:
            guidance_lines.extend(
                [
                    "- You know all evil players (except Mordred if present), "
                    "giving you immense strategic advantage",
                    "- PRIMARY GOAL: Guide resistance to victory WITHOUT revealing you're Merlin",
                    "",
                    "CRITICAL: You KNOW who is evil. USE THIS KNOWLEDGE STRATEGICALLY:",
                    "- When evil players appear on missions that fail, you KNOW they caused it",
                    "- Calculate: Can this mission succeed? (Does it have too many evil players?)",
                    "- DON'T blindly approve teams with known evil 'to avoid suspicion'",
                    "- DO reject suspicious teams, but frame it as 'gut feeling' or "
                    "'wanting different combinations'",
                    "- Pattern Recognition: If evil player X was on failed mission 1 "
                    "and is proposed again - YOU KNOW they'll likely sabotage again",
                    "- Balance: Sometimes approve 1 evil player on larger teams, "
                    "but NEVER when it guarantees failure",
                    "",
                    "- Be subtle: Suggest teams or votes that 'happen' to avoid evil players",
                    "- Cover: Build plausible reasoning that doesn't rely on hidden knowledge",
                    "- WARNING: If Resistance wins 3 missions, Assassin gets to guess "
                    "your identity",
                    "- Think: How would a regular Resistance player act with no knowledge?",
                ]
            )
        elif role == RoleType.PERCIVAL:
            guidance_lines.extend(
                [
                    "- You see Merlin (and Morgana if present), but can't distinguish them",
                    "- PRIMARY GOAL: Help Resistance win 3 missions first, "
                    "identify real Merlin second",
                    "- Secondary goal: Protect Merlin's identity so they survive "
                    "assassination phase",
                    "",
                    "DEDUCTION STRATEGY:",
                    "- Analyze WHO makes decisions that protect/expose your known "
                    "Merlin candidates",
                    "- If one candidate keeps making suspiciously good choices, "
                    "they're likely real Merlin",
                    "- Track which players vote against teams that later fail - "
                    "these are likely good",
                    "",
                    "- Watch: Which of your known players makes subtle, wise decisions?",
                    "- Support: Back Merlin's guidance without drawing attention to them",
                    "- Protect: Help Merlin deflect suspicion onto yourself or others",
                    "- Misdirection: If needed, act like you might be Merlin to confuse Assassin",
                ]
            )
        elif role == RoleType.LOYAL_SERVANT:
            guidance_lines.extend(
                [
                    "- You have no special knowledge, only observation and deduction",
                    "- PRIMARY GOAL: Identify evil players through behavioral analysis",
                    "",
                    "PATTERN ANALYSIS (YOUR ONLY TOOL):",
                    "- YOU MUST DEDUCE from patterns since you have no special knowledge",
                    "- Cross-reference: Which players appear on multiple failed missions?",
                    "- Vote analysis: Who consistently approves teams that fail?",
                    "- Behavior: Who deflects when questioned? Who provides vague reasoning?",
                    "",
                    "- Watch: Who consistently ends up on failed missions?",
                    "- Patterns: Who votes in suspicious ways? Who deflects accusations?",
                    "- Trust: Look for players who demonstrate good judgment",
                    "- Be vocal: Share observations to help coordinate resistance",
                ]
            )
        elif role == RoleType.MINION_OF_MORDRED:
            guidance_lines.extend(
                [
                    "- You know your fellow evil players, allowing coordination",
                    "- PRIMARY GOAL: Fail 3 missions while maintaining cover",
                    "",
                    "SUBTLETY AND COORDINATION:",
                    "- DON'T always fail immediately - build trust first "
                    "(success on round 1 if alone)",
                    "- Coordinate implicitly: If 2+ evil on team, only ONE needs to fail",
                    "- Create plausible deniability: 'I don't know why it failed, "
                    "I played success!'",
                    "- Force Merlin to reveal: Propose teams that Merlin must reject "
                    "to protect Resistance",
                    "",
                    "5TH REJECTION STRATEGY (SUBTLE!):",
                    "- If 5 teams rejected, evil wins - BUT you can't force this at 5th attempt",
                    "- At 4 rejections: Resistance (majority) will ALL approve → team WILL pass",
                    "- If you reject 5th attempt: You expose yourself AND achieve nothing",
                    "- CORRECT strategy: Use rejections 1-4 to force a 5th team WITH evil on it",
                    "- At 5th attempt: APPROVE like resistance would, fail mission if you're on it",
                    "",
                    "- Blend in: Act like resistance, express 'concern' about evil players",
                    "- Coordinate: Ensure missions have enough evil players to fail",
                    "- Strategic fails: Build trust before failing when it matters",
                    "- Voting: Sometimes vote against evil teams to appear good "
                    "(but not on 5th attempt!)",
                ]
            )
        elif role == RoleType.ASSASSIN:
            guidance_lines.extend(
                [
                    "- You're a Minion with a special power: killing Merlin if evil loses",
                    "- PRIMARY GOAL: Fail missions, but if evil loses, identify Merlin",
                    "",
                    "MERLIN HUNTING:",
                    "- During game: Note who makes suspiciously good decisions",
                    "- Force reveals: Create situations where Merlin must guide obviously",
                    "- Mental notes: Track who opposes teams with evil players",
                    "- Final choice: Merlin often tries to be subtle, not the loudest leader",
                    "- Remember: Your assassination guess can steal victory from defeat",
                    "",
                    "BUILD TRUST FIRST:",
                    "- DON'T always fail immediately - success on round 1 if you're alone",
                    "- Coordinate with other evil: If 2+ evil on team, only ONE needs to fail",
                    "- Create plausible deniability for when you do fail missions",
                    "",
                    "5TH REJECTION STRATEGY:",
                    "- At 4 rejections: Don't reject 5th team - you'll just expose yourself",
                    "- Resistance (majority) will approve → team passes regardless of your vote",
                    "- Better play: Approve to blend in, hunt for Merlin as planned",
                    "- Use rejections 1-4 to pressure toward a 5th team with evil on it",
                ]
            )
        elif role == RoleType.MORDRED:
            guidance_lines.extend(
                [
                    "- You're evil AND invisible to Merlin - extremely powerful",
                    "- PRIMARY GOAL: Use your invisibility to infiltrate trusted teams",
                    "- Advantage: Merlin can't warn against you without revealing themselves",
                    "- Strategy: Build trust by appearing cautious about 'other' evil players",
                    "- Pressure: If on missions, you can fail while others suspect known evil",
                    "- Watch: Identify Merlin by who trusts you without apparent reason",
                    "- 5th attempt: Approve to blend in (rejecting exposes you for no benefit)",
                ]
            )
        elif role == RoleType.MORGANA:
            guidance_lines.extend(
                [
                    "- You appear as Merlin to Percival, creating confusion",
                    "- PRIMARY GOAL: Impersonate Merlin to mislead Percival",
                    "- Deception: Make 'wise' suggestions that subtly help evil",
                    "- Mirror: Act like Merlin would - subtle, helpful, but guide wrong",
                    "- Percival bait: Let Percival 'figure out' you're important",
                    "- Misdirection: If evil loses, you might draw the assassination",
                    "- 5th attempt: Approve to maintain cover "
                    "(team passes anyway, don't expose yourself)",
                ]
            )
        elif role == RoleType.OBERON:
            guidance_lines.extend(
                [
                    "- You're evil but don't know other evil players (and they don't know you)",
                    "- PRIMARY GOAL: Fail missions while appearing to hunt for evil",
                    "- Isolation: Use your lack of knowledge as cover - you seem resistance",
                    "- Aggressive: Accuse everyone, including evil, to maintain cover",
                    "- Opportunistic: Fail missions when you're on them",
                    "- Confusion: Your random accusations might actually help evil",
                    "- 5th attempt: Approve like everyone else (rejecting just exposes you)",
                ]
            )

        return "\n".join(guidance_lines)

    def _build_observation_context(self, observation: AgentObservation) -> str:
        """Build a text description of the game state for the agent."""
        lines = [
            "═══ YOUR IDENTITY ═══",
            f"YOU are: {observation.display_name} (player ID: {observation.player_id})",
            f"Your Role: {observation.role.value.replace('_', ' ').title()}",
            f"Your Alignment: {observation.alignment.value.title()}",
            "",
            (
                f"IMPORTANT: YOU are {observation.display_name}. "
                f"When you see '{observation.player_id}' mentioned,"
            ),
            "that refers to YOU. Any other player_id is a DIFFERENT player, not you.",
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
            lines.append("Your special role knowledge:")
            if observation.knowledge.visible_player_ids:
                visible_names = [
                    observation.all_player_names[observation.all_player_ids.index(pid)]
                    for pid in observation.knowledge.visible_player_ids
                ]
                # Make it crystal clear what this knowledge means
                if observation.role == RoleType.MERLIN:
                    lines.append(
                        "  - These players are EVIL "
                        f"(you see them as Merlin): {', '.join(visible_names)}"
                    )
                    lines.append(
                        "  - You MUST use this knowledge to avoid/reject teams "
                        "with these evil players"
                    )
                elif observation.alignment == Alignment.MINION:
                    lines.append(
                        f"  - These are your FELLOW EVIL players: " f"{', '.join(visible_names)}"
                    )
                elif observation.role == RoleType.PERCIVAL:
                    lines.append(
                        "  - These players include Merlin "
                        f"(and Morgana if present): {', '.join(visible_names)}"
                    )
                else:
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

            # Mission pattern analysis
            lines.append("")
            lines.append("MISSION PATTERN ANALYSIS:")

            # Track players on failed missions
            failed_mission_players: dict[str, int] = {}
            for mission in observation.mission_history:
                if mission.result.value == "failure":
                    for pid in mission.team:
                        failed_mission_players[pid] = failed_mission_players.get(pid, 0) + 1

            if failed_mission_players:
                lines.append("Players appearing on multiple FAILED missions (HIGHLY SUSPICIOUS):")
                for pid, count in sorted(failed_mission_players.items(), key=lambda x: -x[1]):
                    if count > 1:
                        player_name = observation.all_player_names[
                            observation.all_player_ids.index(pid)
                        ]
                        lines.append(f"  - {player_name}: {count} failed missions")
            else:
                lines.append("  - No players have been on multiple failed missions yet")

        # Public statements from other players
        if observation.public_statements:
            lines.append("")
            lines.append("Public reasoning from other players:")
            lines.append("(Remember: players may lie or mislead about their reasoning)")
            for player_id, decision_type, statement in observation.public_statements[-10:]:
                player_name = observation.all_player_names[
                    observation.all_player_ids.index(player_id)
                ]
                lines.append(f"  - {player_name} ({decision_type}): {statement}")

        return "\n".join(lines)

    def propose_team(self, observation: AgentObservation) -> TeamProposal:
        """Generate a team proposal using Gemini."""
        game_context = self._build_game_context()
        role_guidance = self._build_role_guidance(observation)
        observation_context = self._build_observation_context(observation)

        # Build previously rejected teams warning
        rejected_teams_warning = ""
        if observation.vote_history:
            recent_rejected = [
                v
                for v in observation.vote_history[-5:]  # Last 5 votes
                if v.round_number == observation.round_number and not v.approved
            ]
            if recent_rejected:
                rejected_teams_warning = "\nPREVIOUSLY REJECTED TEAMS THIS ROUND:\n"
                for vote in recent_rejected:
                    team_names = [
                        observation.all_player_names[observation.all_player_ids.index(pid)]
                        for pid in vote.team
                    ]
                    rejected_teams_warning += (
                        f"  - Attempt {vote.attempt_number}: {', '.join(team_names)}\n"
                    )
                rejected_teams_warning += (
                    "\nYou MUST propose a DIFFERENT team composition. "
                    "Don't repeat what was rejected!\n"
                )

        prompt = f"""{game_context}
{role_guidance}

{observation_context}
{rejected_teams_warning}
DECISION: TEAM PROPOSAL
You are the mission leader. You must propose a team of exactly \
{observation.required_team_size} players.

CRITICAL REQUIREMENT:
- If teams have been rejected this round, you MUST propose a DIFFERENT combination
- Don't propose the exact same players that were just rejected
- Change at least one player to show you're adapting to feedback

Consider:
- Your alignment: Do you want this mission to succeed or fail?
- Your knowledge: What do you know about other players?
- Deception: How can you justify this team regardless of your true role?
- Table dynamics: Who has been trusted/suspected so far?
- Rejection pressure: {observation.consecutive_rejections} rejections so far \
({5 - observation.consecutive_rejections} more = auto-fail)

REASONING REQUIREMENTS:
True Reasoning:
- Reference SPECIFIC patterns/facts from the game history
- Explain how your role knowledge influences this decision
- If changing from rejected teams, explain WHY you're making different choices
- Consider: What does this choice reveal about me? How do I maintain cover?
- Be SPECIFIC about players and their histories, not generic

Public Reasoning (VISIBLE TO ALL PLAYERS):
- Must sound DIFFERENT from other players (avoid copying phrases)
- Should sound plausible for multiple roles (don't reveal your true role)
- If teams were rejected, acknowledge you're trying a different approach
- Keep it concise (1-2 sentences max) and unique to your perspective

!!!!! CRITICAL - PUBLIC REASONING SECURITY !!!!!
NEVER REVEAL YOUR ALIGNMENT IN PUBLIC REASONING:
- WRONG: "I'm evil so I'll..."
- WRONG: "...avoid tipping off the group that I'm evil"
- WRONG: "As a minion, I need to..."
- WRONG: "I'm resistance so I'll..."
- CORRECT: "This team looks balanced" (neutral, reveals nothing)
- CORRECT: "I trust Alice based on her voting pattern" (deduction, not role reveal)
- CORRECT: "We should test this group" (strategic, non-revealing)

If you are EVIL:
- Claim to be good OR stay neutral - NEVER admit being evil
- You can lie about suspicions, trust, observations - anything except your role
- Example GOOD evil public reasoning: "I think Bob is trustworthy based on mission 1"
- Example BAD evil public reasoning: "I'm playing success to hide that I'm evil"

If you are RESISTANCE:
- You can claim to be good (it's true!) or stay neutral
- Don't reveal special knowledge (if Merlin, don't reveal you know who's evil)
- Example: "I approve because this team has proven players" (safe, reveals nothing)

FACT CHECK YOUR REASONING:
Before responding, verify:
- Are you referencing actual game events, not made-up information?
- Is this team DIFFERENT from previously rejected teams this round?
- Do your conclusions follow logically from the evidence?
- Are you using information you actually have access to?
- Does your reasoning contradict any observable facts?

Example mistakes to AVOID:
- Proposing the EXACT same team that was just rejected
- "Team size is strategic" - No, it's determined by rules
- "Everyone played success" when mission failed - Impossible, someone failed
- Generic "gather information" without analyzing information already gathered
- Approving same suspicious players repeatedly without new reasoning

Respond with a JSON object with BOTH true and public reasoning:
{{
  "team": ["player_1", "player_2"],
  "true_reasoning": "your actual strategic thinking (only you see this)",
  "public_reasoning": "what you'll tell other players (they see this - use for deception)"
}}

Your response:"""

        response_text = self._generate_text(prompt)
        parsed = self._parse_json_response(response_text)

        team = tuple(parsed.get("team", []))
        true_reasoning = parsed.get("true_reasoning", "")
        public_reasoning = parsed.get("public_reasoning", "")

        # Validate team size
        if len(team) != observation.required_team_size:
            # Fallback: take first N players if invalid
            team = observation.all_player_ids[: observation.required_team_size]
            true_reasoning = f"Invalid team size, using fallback. Original: {true_reasoning}"

        # CRITICAL: Detect if evil player revealed their alignment in public reasoning
        from .enums import Alignment

        if observation.alignment == Alignment.MINION:
            dangerous_phrases = [
                "evil",
                "minion",
                "mordred",
                "assassin",
                "i'm on the evil team",
                "hide that i'm",
                "avoid tipping",
                "tipping off",
            ]
            public_lower = public_reasoning.lower()
            for phrase in dangerous_phrases:
                if phrase in public_lower:
                    public_reasoning = "This team composition looks balanced and worth testing."
                    true_reasoning += " [WARNING: Removed dangerous phrase from public reasoning]"
                    break

        return TeamProposal(
            team=team,
            true_reasoning=true_reasoning,
            public_reasoning=public_reasoning,
        )

    def vote_on_team(self, observation: AgentObservation) -> VoteDecision:
        """Generate a vote decision using Gemini."""
        from .enums import Alignment

        game_context = self._build_game_context()
        role_guidance = self._build_role_guidance(observation)
        observation_context = self._build_observation_context(observation)

        # Build urgency warning for 5th attempt
        urgency_warning = ""
        if observation.consecutive_rejections >= 4:
            if observation.alignment == Alignment.RESISTANCE:
                urgency_warning = """
!!!!! CRITICAL GAME-ENDING DECISION !!!!!
This is the 5th consecutive team proposal. If this team is rejected, THE GAME ENDS
IMMEDIATELY and EVIL WINS. This is not just a failed mission - it's the END OF THE
ENTIRE GAME. As a RESISTANCE player, you MUST APPROVE this team or you lose everything.
Any team is better than losing the entire game.
APPROVE OR YOU LOSE EVERYTHING.
"""
            else:
                urgency_warning = """
!!!!! CRITICAL 5TH ATTEMPT - STRATEGIC TRAP !!!!!
This is the 5th consecutive team proposal. You might think: "Reject and evil wins!"
BUT WAIT - Think about the math:
- ALL resistance players will approve (or lose the game)
- Resistance has the MAJORITY
- This team WILL PASS no matter how you vote
- If you reject, you reveal you're evil for NO BENEFIT

CORRECT EVIL STRATEGY:
- APPROVE this team (like resistance would)
- Your rejections gained NOTHING except exposing your identity
- The only win was getting evil players ON this team (did you succeed?)
- Blend in now, fail the mission later if you're on it

DO NOT REVEAL YOURSELF BY REJECTING - THE TEAM WILL PASS ANYWAY.
"""

        prompt = f"""{game_context}
{role_guidance}

{observation_context}
{urgency_warning}
DECISION: TEAM VOTE
You must vote to APPROVE or REJECT the proposed team.

CURRENT SITUATION:
- Consecutive rejections so far: {observation.consecutive_rejections}
- Rejections until GAME OVER: {5 - observation.consecutive_rejections}
- 5th rejection consequence: GAME ENDS - EVIL WINS IMMEDIATELY (not just a mission)

Consider:
- Your alignment: Does this team help or hurt your side?
- Your knowledge: Do you recognize any evil/good players on the team?
- Strategic voting: Sometimes voting against your interest can provide cover
- Patterns: Avoid voting in ways that obviously reveal your role

STRATEGIC VOTING CONSIDERATIONS:
- Approving: Means you trust this team will advance your side's goals
- Rejecting: Forces a new proposal, revealing who else the leader trusts
  * Use rejection to: gather information, prevent bad teams, apply pressure
  * CRITICAL: 5 consecutive rejections = GAME OVER, EVIL WINS IMMEDIATELY

ALIGNMENT-SPECIFIC STRATEGY:
If you are RESISTANCE:
- Rejections 1-4: Use strategically to force better team compositions
  * Reject teams with suspicious players or patterns
  * Force information by seeing who else leaders trust
  * The auto-fail won't happen because everyone approves on 5th attempt
- At 4 rejections (5th attempt): You MUST approve or you LOSE THE ENTIRE GAME
  * This is the ONLY truly dangerous rejection
  * Any team is better than instant defeat
- Strategic approach: Be selective on attempts 1-4, always approve on attempt 5

If you are EVIL:
- Early rejections (0-3): Create pressure, force bad teams, approach 5th attempt
- At 4 rejections: Your goal was to get evil ON the 5th team, NOT to reject it
  * If you reject: You reveal yourself AND the team passes anyway (resistance has majority)
  * Correct play: APPROVE like everyone else, blend in, fail mission if you're on it
  * The 5th rejection trap: Rejecting exposes you for zero benefit
- Strategic focus: Use rejections 1-4 to pressure toward a 5th team WITH evil players
- At 5th attempt: Vote approve to maintain cover (the team will pass regardless)

WHEN TO REJECT (if Resistance):
- Team has too many known evil players (and it's NOT the 5th attempt)
- You have knowledge (e.g., Merlin) that team will certainly fail (NOT 5th attempt)
- NEVER EVER on 5th attempt - rejecting = instant game loss

WHEN TO APPROVE (if Resistance):
- It's the 5th attempt (you have no choice - must approve or lose)
- Team avoids repeatedly suspicious players
- You're on the team and can ensure success

WHEN TO APPROVE (if Evil):
- It's the 5th attempt (rejecting reveals you for no benefit - team passes anyway)
- Need to build trust for later betrayals
- Team has good chance to fail anyway

REASONING REQUIREMENTS:
True Reasoning:
- Reference SPECIFIC patterns/facts from the game history
- IF YOU HAVE NO SPECIAL KNOWLEDGE: Deduce from mission failures!
  * Example: "Round 1 team was [Alice, Bob], mission failed → one of them is evil"
  * Example: "Alice on both failed missions → very suspicious"
  * Example: "I played success on mission 2, it still failed → teammate is evil"
- IF YOU HAVE SPECIAL KNOWLEDGE (Merlin, Evil): Use it! Don't ignore known evil players
- Explain how your role knowledge influences this decision
- Consider: What does this choice reveal about me? How do I maintain cover?
- Be SPECIFIC about players and their histories, not generic

Public Reasoning (VISIBLE TO ALL PLAYERS):
- Must sound DIFFERENT from other players (avoid copying phrases)
- Should sound plausible for multiple roles (don't reveal your true role)
- Can include strategic misdirection or partial truths
- Keep it concise (1-2 sentences max) and unique to your perspective

!!!!! CRITICAL - PUBLIC REASONING SECURITY !!!!!
NEVER REVEAL YOUR ALIGNMENT IN PUBLIC REASONING:
- WRONG: "I'm evil so I'll..."
- WRONG: "...to hide that I'm a minion"
- WRONG: "As resistance, I must..."
- CORRECT: "This team looks trustworthy" (neutral)
- CORRECT: "I'm suspicious of Charlie" (deduction-based)

If EVIL: Always claim to be good or stay neutral - NEVER admit being evil
If RESISTANCE: You can claim to be good or stay neutral

FACT CHECK YOUR REASONING:
Before responding, verify:
- Are you referencing actual game events, not made-up information?
- Do your conclusions follow logically from the evidence?
- Does your reasoning contradict any observable facts?
- If you know players are evil, are you acting on that knowledge?

Respond with a JSON object with BOTH true and public reasoning:
{{
  "approve": true,
  "true_reasoning": "your actual strategic thinking (only you see this)",
  "public_reasoning": "what you'll tell other players (they see this)"
}}

Your response:"""

        response_text = self._generate_text(prompt)
        parsed = self._parse_json_response(response_text)

        approve = bool(parsed.get("approve", False))
        true_reasoning = parsed.get("true_reasoning", "")
        public_reasoning = parsed.get("public_reasoning", "")

        # CRITICAL: Detect if evil player revealed their alignment in public reasoning
        if observation.alignment == Alignment.MINION:
            dangerous_phrases = [
                "evil",
                "minion",
                "mordred",
                "assassin",
                "i'm on the evil team",
                "hide that i'm",
                "avoid tipping",
                "tipping off",
            ]
            public_lower = public_reasoning.lower()
            for phrase in dangerous_phrases:
                if phrase in public_lower:
                    public_reasoning = "This team looks balanced and worth testing."
                    true_reasoning += " [WARNING: Removed dangerous phrase from public reasoning]"
                    break

        return VoteDecision(
            approve=approve,
            true_reasoning=true_reasoning,
            public_reasoning=public_reasoning,
        )

    def execute_mission(self, observation: AgentObservation) -> MissionAction:
        """Generate a mission action using Gemini."""
        game_context = self._build_game_context()
        role_guidance = self._build_role_guidance(observation)
        observation_context = self._build_observation_context(observation)
        prompt = f"""{game_context}
{role_guidance}

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

REASONING REQUIREMENTS:
True Reasoning:
- Reference SPECIFIC patterns/facts from the game history
- Explain your strategic choice (if evil: why fail or success now?)
- Consider: What does this reveal about me?
- Be SPECIFIC about the situation, not generic

Public Reasoning (VISIBLE TO ALL PLAYERS):
- Must sound DIFFERENT from other players (avoid copying phrases)
- Should sound plausible for multiple roles
- Explain your contribution to the mission (can be misleading if evil)
- Keep it concise (1-2 sentences max) and unique to your perspective

!!!!! CRITICAL - PUBLIC REASONING SECURITY !!!!!
NEVER REVEAL YOUR ALIGNMENT IN PUBLIC REASONING:
- WRONG: "I'm choosing SUCCESS to hide that I'm evil"
- WRONG: "...avoid tipping off the group that I'm a minion"
- WRONG: "As a resistance player, I must..."
- CORRECT: "I'm playing SUCCESS to support the team" (neutral)
- CORRECT: "I trust this team will succeed" (doesn't reveal role)

If EVIL: Claim you're supporting the mission OR express caution - NEVER say you're evil
If RESISTANCE: You can say you're supporting the mission

FACT CHECK YOUR REASONING:
Before responding, verify:
- Are you referencing actual game events?
- Does your reasoning make logical sense?
- If you claim you played success but mission failed, is that plausible?

Respond with a JSON object with BOTH true and public reasoning:
{{
  "success": true,    // true = play SUCCESS card, false = play FAIL card
  "true_reasoning": "your actual strategic thinking (only you see this)",
  "public_reasoning": "what you'll tell other players (they see this)"
}}

IMPORTANT JSON RESPONSE RULES:
- "success": true means you play a SUCCESS card
- "success": false means you play a FAIL card
- If you are RESISTANCE: You MUST use "success": true (you cannot fail)
- If you are EVIL and want to FAIL the mission: Use "success": false
- If you are EVIL and want to play SUCCESS (for cover): Use "success": true

Examples:
- Evil sabotaging: {{"success": false, "true_reasoning": "I'm failing to...",
  "public_reasoning": "Supporting team"}}
- Evil blending: {{"success": true, "true_reasoning": "Build trust",
  "public_reasoning": "I trust this team"}}
- Resistance: {{"success": true, "true_reasoning": "Must play success",
  "public_reasoning": "Supporting mission"}}

Your response:"""

        response_text = self._generate_text(prompt)
        parsed = self._parse_json_response(response_text)

        success = bool(parsed.get("success", False))
        true_reasoning = parsed.get("true_reasoning", "")
        public_reasoning = parsed.get("public_reasoning", "")

        # Force resistance to play success
        from .enums import Alignment

        if observation.alignment == Alignment.RESISTANCE:
            success = True
            if not parsed.get("success", True):
                true_reasoning += " [Forced to SUCCESS - Resistance player]"

        # CRITICAL: Detect if evil player revealed their alignment in public reasoning
        if observation.alignment == Alignment.MINION:
            dangerous_phrases = [
                "evil",
                "minion",
                "mordred",
                "assassin",
                "bad",
                "i'm on the evil team",
                "hide that i'm",
                "avoid tipping",
                "tipping off",
                "that i'm a",
            ]
            public_lower = public_reasoning.lower()
            for phrase in dangerous_phrases:
                if phrase in public_lower:
                    # Remove the dangerous phrase and replace with safe alternative
                    public_reasoning = "I'm supporting this decision to help the team succeed."
                    true_reasoning += (
                        f" [WARNING: Removed dangerous phrase '{phrase}' from public reasoning]"
                    )
                    break

        return MissionAction(
            success=success,
            true_reasoning=true_reasoning,
            public_reasoning=public_reasoning,
        )

    def guess_merlin(self, observation: AgentObservation) -> AssassinationGuess:
        """Generate an assassination guess using Gemini."""
        game_context = self._build_game_context()
        role_guidance = self._build_role_guidance(observation)
        observation_context = self._build_observation_context(observation)
        prompt = f"""{game_context}
{role_guidance}

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

REASONING REQUIREMENTS:
True Reasoning:
- Analyze SPECIFIC voting and team patterns from each player
- Reference concrete examples of suspicious behavior
- Explain your deduction process step by step
- Consider alternative candidates and why you ruled them out

Public Reasoning:
- Explain your choice to other players
- Can be honest analysis or misdirection
- Keep it concise (1-2 sentences)

FACT CHECK YOUR REASONING:
Before responding, verify:
- Are you analyzing actual game events and votes?
- Does your analysis follow logical deduction?
- Have you considered all Resistance players, not just vocal ones?

Respond with a JSON object with BOTH true and public reasoning:
{{
  "target_id": "player_3",
  "true_reasoning": "your actual analysis (only you see this)",
  "public_reasoning": "what you'll tell other players (they see this)"
}}

Your response:"""

        response_text = self._generate_text(prompt)
        parsed = self._parse_json_response(response_text)

        target_id = parsed.get("target_id", observation.all_player_ids[0])
        true_reasoning = parsed.get("true_reasoning", "")
        public_reasoning = parsed.get("public_reasoning", "")

        # Validate target exists
        if target_id not in observation.all_player_ids:
            target_id = observation.all_player_ids[0]
            true_reasoning = f"Invalid target, using fallback. Original: {true_reasoning}"

        return AssassinationGuess(
            target_id=target_id,
            true_reasoning=true_reasoning,
            public_reasoning=public_reasoning,
        )

    def make_statement(
        self, observation: AgentObservation, phase: DiscussionPhase
    ) -> DiscussionResponse:
        """Generate a discussion statement using the LLM."""
        game_context = self._build_game_context()
        role_guidance = self._build_role_guidance(observation)
        observation_context = self._build_observation_context(observation)

        # Build discussion context
        discussion_context = self._build_discussion_context(observation, phase)

        # Phase-specific prompts
        mission_result = "UNKNOWN"
        if phase == DiscussionPhase.POST_MISSION_RESULT and observation.mission_history:
            last_mission = observation.mission_history[-1]
            mission_result = "SUCCESS" if last_mission.result.name == "SUCCESS" else "FAILED"

        # Get leader name for clarity
        leader_name = observation.all_player_names[
            observation.all_player_ids.index(observation.current_leader_id)
        ]

        # Build phase-specific guidance with proper team context
        if phase == DiscussionPhase.PRE_PROPOSAL:
            phase_guidance_text = (
                f"This is BEFORE the team proposal. NO TEAM HAS BEEN PROPOSED YET. "
                f"The leader ({leader_name}) will propose after this discussion. "
                f"You can suggest who you think would be good team members, but "
                f"DO NOT say 'I propose' unless you ARE {leader_name}."
            )
        elif phase == DiscussionPhase.PRE_VOTE:
            team_names = (
                [
                    observation.all_player_names[observation.all_player_ids.index(pid)]
                    for pid in observation.current_team
                ]
                if observation.current_team
                else []
            )
            team_display = ", ".join(team_names) if team_names else "UNKNOWN"
            phase_guidance_text = (
                f"A team HAS been proposed by {leader_name}: {team_display}. "
                f"This is the ACTUAL team on the table. Discuss whether you trust "
                f"THIS SPECIFIC team or have concerns about these specific members."
            )
        elif phase == DiscussionPhase.POST_MISSION_RESULT:
            phase_guidance_text = (
                f"Mission result: {mission_result}. Discuss what this reveals "
                f"about team members or who might be evil."
            )
        elif phase == DiscussionPhase.PRE_ASSASSINATION:
            phase_guidance_text = (
                "Evil has lost, but the Assassin can win by killing Merlin. "
                "Discuss who you think Merlin might be (or deflect if you ARE Merlin)."
            )
        else:
            phase_guidance_text = "Discuss the current game state."

        prompt = f"""{game_context}
{role_guidance}

{observation_context}

{discussion_context}

CRITICAL DISCUSSION CONTEXT:
DISCUSSION PHASE: {phase.value}
{phase_guidance_text}

!!!!! WHO YOU ARE (READ CAREFULLY) !!!!!
YOU are {observation.display_name} (player_id: {observation.player_id})

CRITICAL IDENTITY RULES:
1. When talking about YOURSELF, use "I", "me", "my" - NEVER say "{observation.display_name}"
2. When talking about OTHER players, use their names: {', '.join(
    [n for n in observation.all_player_names if n != observation.display_name]
)}
3. DO NOT say things like "{observation.display_name} should..." or
   "I'd like to hear {observation.display_name}'s take"
4. If you want to talk about yourself, say "I" not your name
5. You are NOT {leader_name} unless your name is literally {leader_name}

EXAMPLES OF CORRECT vs WRONG:
- WRONG: "{observation.display_name} is concerned about Alice"
- CORRECT: "I'm concerned about Alice"
- WRONG: "I want to hear {observation.display_name}'s opinion"
- CORRECT: "I want to hear Bob's opinion" (talking about another player)
- WRONG: "{observation.display_name} will watch carefully"
- CORRECT: "I'll watch carefully"

CURRENT GAME MECHANICS:
- The LEADER this round is: {leader_name} ({observation.current_leader_id})
- Only the LEADER proposes teams - other players discuss but don't propose
- Required team size for this mission: {observation.required_team_size} players
- DO NOT propose teams unless you ARE the leader ({leader_name})
- DO NOT suggest team sizes different from {observation.required_team_size}

CRITICAL - READ THE ACTUAL GAME STATE:
- If discussion is PRE_PROPOSAL: NO team has been proposed yet, only suggestions
- If discussion is PRE_VOTE: A team HAS been proposed, it's listed above in the game state
- DO NOT make up team compositions that aren't shown in the game state
- DO NOT refer to teams that haven't been proposed yet
- ALWAYS refer to players by their ACTUAL names from the player list above

ROLE-SPECIFIC DISCUSSION GUIDANCE:
{(
    "- You are Merlin. You know who the evil players are, but MUST NOT reveal "
    "this directly or you'll be assassinated."
) if observation.role == RoleType.MERLIN else ""}
{(
    "- You are a Minion of Mordred. Consider subtle misdirection, defending "
    "evil teammates, or sowing confusion."
) if observation.role in [
    RoleType.MINION_OF_MORDRED, RoleType.ASSASSIN, RoleType.MORGANA,
    RoleType.MORDRED, RoleType.OBERON
] else ""}
{(
    "- You are a Loyal Servant. Use deduction and social reads to identify "
    "suspicious behavior."
) if observation.role in [RoleType.LOYAL_SERVANT, RoleType.PERCIVAL] else ""}
{(
    "- You are Percival. You know Merlin and Morgana (but not which is which). "
    "Protect Merlin without revealing them."
) if observation.role == RoleType.PERCIVAL else ""}

DISCUSSION STRATEGY:
- Be concise (1-3 sentences)
- Reference specific game events (votes, mission results, proposals)
- Share suspicions about OTHER players (not yourself!), defend yourself, or respond to others
- Consider what information you can reveal without exposing your role
- Evil players: Blend in, defend teammates subtly, cast doubt on good players
- Good players: Share reasoning, ask questions, build trust
- Remember: You discuss, the leader ({leader_name}) proposes

REASONING REQUIREMENTS:
True Reasoning:
- Your actual strategic thinking (only you see this)
- What information you're using (including hidden role knowledge)
- Why you're saying what you're saying

Public Message:
- What other players will see and hear
- Can be honest analysis or strategic misdirection
- Should sound natural and conversational
- Use first person ("I think...", "I trust...", "I'm concerned about...")

FACT CHECK YOUR STATEMENT:
Before responding, verify:
- Are you using "I/me/my" when talking about yourself?
  NOT saying "{observation.display_name}"?
- If you mention {observation.display_name}, you are talking about yourself
  in 3rd person - WRONG!
- Are you speaking as YOURSELF, not referring to yourself as another player?
- If PRE_PROPOSAL: Are you making suggestions, not proposing?
  (only {leader_name} proposes)
- If PRE_VOTE: Are you referring to the ACTUAL proposed team shown
  in the game state?
- Are you using player names that ACTUALLY EXIST in the roster above?
- Does your statement reference actual game events, not made-up information?
- Are you being appropriately subtle about your role knowledge?
- Read your message: does it contain your own name ({observation.display_name})?
  If YES, rewrite using "I"!
- Is your message consistent with what you've said before?

Respond with a JSON object:
{{
  "message": "What you'll say to all players (keep concise)",
  "true_reasoning": "Your actual strategic thinking (only you see this)"
}}

Your response:"""

        response_text = self._generate_text(prompt)
        parsed = self._parse_json_response(response_text)

        message = parsed.get("message", "I'll pass for now.")
        true_reasoning = parsed.get("true_reasoning", "")

        return DiscussionResponse(message=message, true_reasoning=true_reasoning)

    def _build_discussion_context(
        self, observation: AgentObservation, phase: DiscussionPhase
    ) -> str:
        """Build context about the current discussion including recent statements."""
        if not observation.discussion_statements:
            return "DISCUSSION: This is the first statement in this discussion phase."

        # Show recent statements (last 10 to avoid token bloat)
        recent = observation.discussion_statements[-10:]
        statements_text = "\n".join(
            [
                (
                    f"- {stmt.speaker_id} ({stmt.phase.value}, "
                    f'Round {stmt.round_number}): "{stmt.message}"'
                )
                for stmt in recent
            ]
        )

        return f"""RECENT DISCUSSION:
{statements_text}

Consider these statements when crafting your response. You can agree, disagree,
ask questions, or change the topic."""

    def _parse_json_response(self, response_text: str) -> dict[str, Any]:
        """Parse JSON from LLM response, handling markdown code blocks and text before JSON."""
        text = response_text.strip()

        # Try to find JSON in the response - look for first { and last }
        first_brace = text.find("{")
        last_brace = text.rfind("}")

        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            # Extract just the JSON part
            json_text = text[first_brace : last_brace + 1]
            try:
                return json.loads(json_text)
            except json.JSONDecodeError:
                pass  # Fall through to other parsing attempts

        # Try removing markdown code blocks
        if "```" in text:
            lines = text.split("\n")
            in_code_block = False
            code_lines = []
            for line in lines:
                if line.strip().startswith("```"):
                    in_code_block = not in_code_block
                elif in_code_block:
                    code_lines.append(line)
            if code_lines:
                text = "\n".join(code_lines)

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            # Log the parsing failure for debugging
            print(f"Warning: Failed to parse JSON response: {e}")
            print(f"Response text (first 200 chars): {response_text[:200]}...")
            # Return empty dict as fallback
            return {}


@dataclass
class GeminiClient(BaseLLMClient):
    """Google Gemini API client for agent decision-making.

    Uses Gemma 3 model for fast, cost-effective gameplay with higher rate limits.
    Requires GEMINI_API_KEY environment variable.

    Rate limiting: Gemma 3 has a 30 RPM limit. We add a 2.1s delay between
    requests to stay under this limit (60s / 30 requests = 2s per request,
    plus small buffer).
    """

    model_name: str = "gemma-3-12b-it"
    temperature: float = 0.7
    api_key: str | None = None
    max_retries: int = 3
    base_retry_delay: float = 1.0
    request_delay: float = 2.1  # Delay between requests to stay under 30 RPM

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
        self._last_request_time: float = 0.0

    def _generate_text(self, prompt: str) -> str:
        """Generate text completion from prompt with retry logic for rate limits."""
        # Proactive rate limiting: ensure minimum delay between requests
        current_time = time.time()
        time_since_last_request = current_time - self._last_request_time
        if time_since_last_request < self.request_delay:
            sleep_time = self.request_delay - time_since_last_request
            time.sleep(sleep_time)

        self._last_request_time = time.time()
        last_exception = None

        for attempt in range(self.max_retries):
            try:
                response = self._model.generate_content(
                    prompt,
                    generation_config=genai.GenerationConfig(
                        temperature=self.temperature,
                        max_output_tokens=1000,
                    ),
                )
                return response.text
            except google_exceptions.ResourceExhausted as exc:
                last_exception = exc
                # Extract retry delay from error message if available
                retry_delay = self.base_retry_delay * (2**attempt)  # Exponential backoff

                # Try to parse the suggested retry delay from the error
                error_str = str(exc)
                if "retry in" in error_str.lower():
                    try:
                        # Extract number before 's' in "Please retry in X.XXXs"
                        import re

                        match = re.search(r"retry in ([\d.]+)s", error_str)
                        if match:
                            retry_delay = float(match.group(1))
                    except (ValueError, AttributeError):
                        pass  # Use exponential backoff if parsing fails

                if attempt < self.max_retries - 1:
                    retry_msg = (
                        f"Rate limit hit. Waiting {retry_delay:.1f}s "
                        f"before retry {attempt + 1}/{self.max_retries}..."
                    )
                    print(retry_msg)
                    time.sleep(retry_delay)
                else:
                    # Last attempt failed, raise the exception
                    raise
            except Exception:
                # For non-rate-limit errors, fail immediately
                raise

        # Should never reach here, but just in case
        if last_exception:
            raise last_exception
        raise RuntimeError("Unexpected state in _generate_text retry logic")


__all__ = ["GeminiClient", "BaseLLMClient", "LLMClient"]
