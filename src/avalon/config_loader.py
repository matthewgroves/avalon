"""YAML configuration file loader for game setup."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from .config import GameConfig
from .enums import PlayerType, RoleType
from .exceptions import ConfigurationError
from .interaction import BriefingDeliveryMode, BriefingOptions
from .roles import build_role_list
from .setup import PlayerRegistration


@dataclass(frozen=True, slots=True)
class GameSetupConfig:
    """Complete game setup loaded from configuration file."""

    game_config: GameConfig
    registrations: tuple[PlayerRegistration, ...]
    briefing_options: BriefingOptions


def load_config_file(config_path: str | Path) -> GameSetupConfig:
    """Load game configuration from a YAML file.

    Args:
        config_path: Path to the YAML configuration file.

    Returns:
        GameSetupConfig containing game configuration, player registrations, and briefing options.

    Raises:
        ConfigurationError: If the file is invalid or missing required fields.
        FileNotFoundError: If the config file doesn't exist.
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with path.open("r") as f:
        try:
            data: dict[str, Any] = yaml.safe_load(f)
        except yaml.YAMLError as exc:
            raise ConfigurationError(f"Invalid YAML file: {exc}") from exc

    if not isinstance(data, dict):
        raise ConfigurationError("Config file must contain a YAML mapping")

    # Parse player setup
    player_data = data.get("players")
    if not player_data:
        raise ConfigurationError("Config file must specify 'players' list")
    if not isinstance(player_data, list):
        raise ConfigurationError("'players' must be a list")

    # Parse player registrations - support both string format and dict format
    registrations: list[PlayerRegistration] = []
    for idx, player_entry in enumerate(player_data):
        if isinstance(player_entry, str):
            # Simple format: just player name (defaults to human)
            registrations.append(
                PlayerRegistration(display_name=player_entry, player_type=PlayerType.HUMAN)
            )
        elif isinstance(player_entry, dict):
            # Structured format: {name: "Alice", type: "agent"}
            name = player_entry.get("name")
            if not name:
                raise ConfigurationError(f"Player entry {idx + 1} missing 'name' field")

            type_str = player_entry.get("type", "human")
            if not isinstance(type_str, str):
                raise ConfigurationError(f"Player {name}: 'type' must be a string")

            type_lower = type_str.lower().strip()
            if type_lower == "human":
                player_type = PlayerType.HUMAN
            elif type_lower == "agent":
                player_type = PlayerType.AGENT
            else:
                raise ConfigurationError(
                    f"Player {name}: invalid type '{type_str}'. Must be 'human' or 'agent'"
                )

            registrations.append(
                PlayerRegistration(display_name=str(name), player_type=player_type)
            )
        else:
            raise ConfigurationError(
                f"Player entry {idx + 1} must be a string or dict with 'name' field"
            )

    player_count = len(registrations)
    registrations_tuple = tuple(registrations)

    # Parse optional special roles
    optional_roles_raw = data.get("optional_roles", [])
    if not isinstance(optional_roles_raw, list):
        raise ConfigurationError("'optional_roles' must be a list")

    # Map simple names to RoleType enum
    role_name_map = {
        "merlin": RoleType.MERLIN,
        "percival": RoleType.PERCIVAL,
        "assassin": RoleType.ASSASSIN,
        "morgana": RoleType.MORGANA,
        "mordred": RoleType.MORDRED,
        "oberon": RoleType.OBERON,
        "loyal_servant": RoleType.LOYAL_SERVANT,
        "minion": RoleType.MINION_OF_MORDRED,
    }

    optional_roles: list[RoleType] = []
    for role_name in optional_roles_raw:
        role_key = str(role_name).lower().strip()
        if role_key not in role_name_map:
            raise ConfigurationError(
                f"Unknown role type: {role_name}. "
                f"Available: {', '.join(sorted(role_name_map.keys()))}"
            )
        optional_roles.append(role_name_map[role_key])

    # Build role list
    roles = build_role_list(player_count, optional_roles=optional_roles if optional_roles else None)

    # Parse briefing options
    briefing_config = data.get("briefing", {})
    if not isinstance(briefing_config, dict):
        raise ConfigurationError("'briefing' must be a mapping")

    briefing_mode_str = briefing_config.get("mode", "sequential")
    try:
        briefing_mode = BriefingDeliveryMode(briefing_mode_str.lower())
    except ValueError:
        raise ConfigurationError(
            f"Invalid briefing mode: {briefing_mode_str}. Must be 'sequential' or 'batch'"
        ) from None

    pause_before = briefing_config.get("pause_before_each", False)
    pause_after = briefing_config.get("pause_after_each", False)

    if not isinstance(pause_before, bool):
        raise ConfigurationError("'briefing.pause_before_each' must be true or false")
    if not isinstance(pause_after, bool):
        raise ConfigurationError("'briefing.pause_after_each' must be true or false")

    briefing_options = BriefingOptions(
        mode=briefing_mode,
        pause_before_each=pause_before,
        pause_after_each=pause_after,
    )

    # Parse optional game settings
    random_seed = data.get("random_seed")
    if random_seed is not None and not isinstance(random_seed, int):
        raise ConfigurationError("'random_seed' must be an integer")

    lady_of_lake = data.get("lady_of_the_lake_enabled", False)
    if not isinstance(lady_of_lake, bool):
        raise ConfigurationError("'lady_of_the_lake_enabled' must be true or false")

    game_config = GameConfig(
        player_count=player_count,
        roles=roles,
        lady_of_the_lake_enabled=lady_of_lake,
        random_seed=random_seed,
    )

    return GameSetupConfig(
        game_config=game_config,
        registrations=registrations_tuple,
        briefing_options=briefing_options,
    )
