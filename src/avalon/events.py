"""Structured event logging for Avalon game sessions."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Iterable, Mapping, Sequence, Tuple, Union, cast

if TYPE_CHECKING:  # pragma: no cover - import only for type hints
    from .enums import Alignment


class GameEventType(str, Enum):
    """Enumerates high-level events emitted by the game engine."""

    PHASE_CHANGED = "phase_changed"
    TEAM_PROPOSED = "team_proposed"
    TEAM_VOTE_RECORDED = "team_vote_recorded"
    MISSION_RESOLVED = "mission_resolved"
    MISSION_AUTO_FAILED = "mission_auto_failed"
    ASSASSINATION_RESOLVED = "assassination_resolved"
    GAME_COMPLETED = "game_completed"
    DISCUSSION_STATEMENT = "discussion_statement"


class EventVisibility(str, Enum):
    """Indicates who should have access to an event payload."""

    PUBLIC = "public"
    PRIVATE = "private"


@dataclass(frozen=True, slots=True)
class GameEvent:
    """Immutable event record captured during play."""

    timestamp: datetime
    type: GameEventType
    payload: Mapping[str, Any] = field(default_factory=dict)
    visibility: EventVisibility = EventVisibility.PUBLIC
    audience: Tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        """Convert the event into a JSON-serialisable dictionary."""

        return {
            "timestamp": self.timestamp.isoformat(),
            "type": self.type.value,
            "payload": dict(self.payload),
            "visibility": self.visibility.value,
            "audience": list(self.audience),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "GameEvent":
        """Reconstruct an event from a dictionary produced by :meth:`to_dict`."""

        timestamp_str = data.get("timestamp")
        if not isinstance(timestamp_str, str):  # pragma: no cover - defensive
            raise ValueError("Event timestamp must be a string")
        payload = data.get("payload") or {}
        if not isinstance(payload, Mapping):  # pragma: no cover - defensive
            raise ValueError("Event payload must be a mapping")
        visibility_raw = data.get("visibility", EventVisibility.PUBLIC.value)
        visibility = EventVisibility(visibility_raw)
        audience_raw = data.get("audience") or []
        if not isinstance(audience_raw, (list, tuple)):
            raise ValueError("Event audience must be a list or tuple")
        audience = tuple(str(item) for item in audience_raw)
        return cls(
            timestamp=datetime.fromisoformat(timestamp_str),
            type=GameEventType(data["type"]),
            payload=dict(payload),
            visibility=visibility,
            audience=audience,
        )


class EventLog:
    """Append-only in-memory log of :class:`GameEvent` instances."""

    def __init__(self, events: Sequence[GameEvent] | None = None) -> None:
        self._events: list[GameEvent] = list(events) if events else []

    def record(
        self,
        event_type: GameEventType,
        payload: Mapping[str, Any] | None = None,
        *,
        timestamp: datetime | None = None,
        visibility: EventVisibility | None = None,
        audience: Sequence[str] | None = None,
    ) -> GameEvent:
        """Append a new event to the log and return it."""

        event_payload = dict(payload or {})
        event = GameEvent(
            timestamp=timestamp or datetime.now(timezone.utc),
            type=event_type,
            payload=event_payload,
            visibility=visibility or EventVisibility.PUBLIC,
            audience=tuple(audience or ()),
        )
        self._events.append(event)
        return event

    @property
    def events(self) -> tuple[GameEvent, ...]:
        """Return all events recorded so far."""

        return tuple(self._events)

    def __len__(self) -> int:  # pragma: no cover - trivial
        return len(self._events)

    def clear(self) -> None:  # pragma: no cover - future use
        self._events.clear()

    def to_jsonl(self) -> str:
        """Serialise the event log to newline-delimited JSON."""

        return "\n".join(
            json.dumps(event.to_dict(), separators=(",", ":")) for event in self._events
        )

    @classmethod
    def from_jsonl(cls, raw: str) -> "EventLog":
        """Create a log from newline-delimited JSON produced by :meth:`to_jsonl`."""

        lines = [line for line in raw.splitlines() if line.strip()]
        events = [GameEvent.from_dict(json.loads(line)) for line in lines]
        return cls(events)

    @classmethod
    def from_events(cls, events: Iterable[GameEvent]) -> "EventLog":
        """Construct a log using the provided events sequence."""

        return cls(list(events))

    def query(
        self,
        *,
        audience_tags: Sequence[str] | None = None,
        include_public: bool = True,
        include_private: bool = False,
    ) -> tuple[GameEvent, ...]:
        """Return events filtered according to audience visibility."""

        allowed_tags = set(audience_tags or ())
        matched: list[GameEvent] = []
        for event in self._events:
            if include_public and event.visibility is EventVisibility.PUBLIC:
                matched.append(event)
                continue
            if include_private:
                matched.append(event)
                continue
            if allowed_tags and any(tag in allowed_tags for tag in event.audience):
                matched.append(event)
        return tuple(matched)

    def public_events(self) -> tuple[GameEvent, ...]:
        """Return only public events."""

        return self.query(audience_tags=(), include_public=True, include_private=False)

    def events_for_player(
        self,
        player_id: str,
        *,
        extra_tags: Sequence[str] | None = None,
        include_private: bool = False,
    ) -> tuple[GameEvent, ...]:
        """Return events visible to a specific player identifier."""

        tags = [player_audience_tag(player_id)]
        if extra_tags:
            tags.extend(extra_tags)
        return self.query(audience_tags=tags, include_public=True, include_private=include_private)

    def events_for_alignment(
        self,
        alignment: Union["Alignment", str],
        *,
        include_private: bool = False,
    ) -> tuple[GameEvent, ...]:
        """Return events visible to the given alignment."""

        return self.query(
            audience_tags=[alignment_audience_tag(alignment)],
            include_public=True,
            include_private=include_private,
        )


def player_audience_tag(player_id: str) -> str:
    """Construct the audience tag for a specific player."""

    return f"player:{player_id}"


def alignment_audience_tag(alignment: Union["Alignment", str]) -> str:
    """Construct the audience tag used for alignment-scoped events."""

    if hasattr(alignment, "value"):
        enum_alignment = cast("Alignment", alignment)
        return f"alignment:{enum_alignment.value}"
    return f"alignment:{alignment}"


__all__ = [
    "EventLog",
    "EventVisibility",
    "GameEvent",
    "GameEventType",
    "alignment_audience_tag",
    "player_audience_tag",
]
