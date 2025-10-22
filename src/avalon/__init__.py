"""Avalon game engine package."""

from .config import GameConfig, MissionConfig
from .game_state import (
    GamePhase,
    GameState,
    MissionAction,
    MissionDecision,
    MissionRecord,
    MissionResult,
    MissionSummary,
    VoteRecord,
)
from .interaction import (
    CLIInteraction,
    InteractionEventType,
    InteractionIO,
    InteractionLogEntry,
    InteractionResult,
    run_interactive_game,
)
from .knowledge import KnowledgePacket, compute_setup_knowledge
from .players import AgentHook, Player, PlayerId
from .roles import (
    DEFAULT_ROLE_SET_BY_PLAYER_COUNT,
    ROLE_DEFINITIONS,
    RoleDefinition,
    RoleTag,
    default_roles_for_player_count,
    is_minion,
    is_resistance,
    role_alignment,
    validate_role_selection,
)
from .setup import PlayerBriefing, PlayerRegistration, SetupResult, perform_setup

__all__ = [
    "AgentHook",
    "DEFAULT_ROLE_SET_BY_PLAYER_COUNT",
    "GameConfig",
    "GamePhase",
    "GameState",
    "InteractionEventType",
    "InteractionIO",
    "CLIInteraction",
    "InteractionLogEntry",
    "InteractionResult",
    "KnowledgePacket",
    "MissionConfig",
    "MissionAction",
    "MissionDecision",
    "MissionRecord",
    "MissionResult",
    "MissionSummary",
    "Player",
    "PlayerId",
    "PlayerBriefing",
    "PlayerRegistration",
    "ROLE_DEFINITIONS",
    "RoleDefinition",
    "RoleTag",
    "SetupResult",
    "compute_setup_knowledge",
    "default_roles_for_player_count",
    "is_minion",
    "is_resistance",
    "perform_setup",
    "role_alignment",
    "run_interactive_game",
    "validate_role_selection",
    "VoteRecord",
]
