"""Enumerations for Avalon game entities."""

from __future__ import annotations

from enum import Enum


class Alignment(str, Enum):
    """Team alignment in Avalon."""

    RESISTANCE = "resistance"
    MINION = "minion"


class RoleType(str, Enum):
    """Supported Avalon role identities."""

    MERLIN = "merlin"
    PERCIVAL = "percival"
    LOYAL_SERVANT = "loyal_servant_of_arthur"
    ASSASSIN = "assassin"
    MORGANA = "morgana"
    MORDRED = "mordred"
    OBERON = "oberon"
    MINION_OF_MORDRED = "minion_of_mordred"
