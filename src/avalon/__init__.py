"""Avalon game engine package."""

from .config import GameConfig, MissionConfig
from .events import (
    EventLog,
    EventVisibility,
    GameEvent,
    GameEventType,
    alignment_audience_tag,
    player_audience_tag,
)
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
from .persistence import GameStateSnapshot, restore_game_state, snapshot_game_state
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
    "EventLog",
    "GameEvent",
    "GameEventType",
    "EventVisibility",
    "GamePhase",
    "GameState",
    "GameStateSnapshot",
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
    "alignment_audience_tag",
    "player_audience_tag",
    "restore_game_state",
    "role_alignment",
    "run_interactive_game",
    "snapshot_game_state",
    "validate_role_selection",
    "VoteRecord",
]
