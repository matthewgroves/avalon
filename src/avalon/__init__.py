"""Avalon game engine package."""

from .config import GameConfig, MissionConfig
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

__all__ = [
    "AgentHook",
    "DEFAULT_ROLE_SET_BY_PLAYER_COUNT",
    "GameConfig",
    "KnowledgePacket",
    "MissionConfig",
    "Player",
    "PlayerId",
    "ROLE_DEFINITIONS",
    "RoleDefinition",
    "RoleTag",
    "compute_setup_knowledge",
    "default_roles_for_player_count",
    "is_minion",
    "is_resistance",
    "role_alignment",
    "validate_role_selection",
]
