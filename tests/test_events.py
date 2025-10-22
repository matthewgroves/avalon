from __future__ import annotations

from datetime import datetime, timezone

from avalon.enums import Alignment
from avalon.events import (
    EventLog,
    EventVisibility,
    GameEvent,
    GameEventType,
    alignment_audience_tag,
    player_audience_tag,
)


def test_record_defaults_to_public_visibility() -> None:
    log = EventLog()
    event = log.record(GameEventType.PHASE_CHANGED, {"phase": "team_vote"})

    assert event.visibility is EventVisibility.PUBLIC
    assert event.audience == ()
    assert log.public_events() == (event,)


def test_serialisation_round_trip_preserves_visibility_metadata() -> None:
    original = GameEvent(
        timestamp=datetime.now(timezone.utc),
        type=GameEventType.TEAM_VOTE_RECORDED,
        payload={"round": 1},
        visibility=EventVisibility.PRIVATE,
        audience=(player_audience_tag("p1"), alignment_audience_tag(Alignment.MINION)),
    )

    restored = GameEvent.from_dict(original.to_dict())
    assert restored == original


def test_player_and_alignment_filters_include_authorised_private_events() -> None:
    log = EventLog()
    public_event = log.record(GameEventType.PHASE_CHANGED, {"phase": "mission"})
    private_player_event = log.record(
        GameEventType.TEAM_PROPOSED,
        {"leader_id": "p1"},
        visibility=EventVisibility.PRIVATE,
        audience=[player_audience_tag("p1")],
    )
    private_alignment_event = log.record(
        GameEventType.MISSION_RESOLVED,
        {"result": "success"},
        visibility=EventVisibility.PRIVATE,
        audience=[alignment_audience_tag("minion")],
    )

    assert private_player_event in log.events_for_player("p1")
    assert private_player_event not in log.events_for_player("p2")
    assert private_alignment_event in log.events_for_alignment(Alignment.MINION)
    assert private_alignment_event not in log.events_for_alignment(Alignment.RESISTANCE)
    assert public_event in log.events_for_player("p1")
    assert private_player_event not in log.public_events()
    assert private_alignment_event not in log.public_events()
