# Events and Persistence

Avalon's logging and persistence layers enable reproducible gameplay, agent training, and detailed analytics. This guide explains the event schema, visibility metadata, and how to save and restore game state.

## Game Events

Game events capture high-level state transitions within `GameState`. The `EventLog` class manages an append-only list of `GameEvent` records.

```python
from avalon.events import EventLog, GameEventType

log = EventLog()
log.record(GameEventType.TEAM_PROPOSED, {"round": 1, "leader_id": "player_1"})
```

### Event Fields

| Field | Description |
| --- | --- |
| `timestamp` | UTC datetime of the event |
| `type` | One of `GameEventType` (e.g., `PHASE_CHANGED`, `MISSION_RESOLVED`) |
| `payload` | JSON-serialisable dictionary with event-specific data |
| `visibility` | `PUBLIC` or `PRIVATE` |
| `audience` | Tuple of audience tags (e.g., `player:player_1`, `alignment:MINION`) |

Events default to `PUBLIC`. Private events are delivered only to players or alignments whose tags appear in `audience` unless the consumer explicitly requests private data.

### Filtering Events

`EventLog` exposes helper methods to slice the log for downstream consumers:

- `public_events()` – Only events marked `PUBLIC`.
- `events_for_player(player_id)` – Public events plus private events tagged for the given player.
- `events_for_alignment(alignment)` – Public events plus those tagged for the specified alignment.
- `query(...)` – Custom retrieval with explicit audience tags and visibility flags.

Audience tags are constructed with utilities:

```python
from avalon.events import alignment_audience_tag, player_audience_tag

alignment_tag = alignment_audience_tag("MINION")  # -> "alignment:MINION"
player_tag = player_audience_tag("player_1")       # -> "player:player_1"
```

### Serialising Event Logs

- `EventLog.to_jsonl()` – Serialises the log to newline-delimited JSON.
- `EventLog.from_jsonl(raw)` – Recreates a log from JSONL text.
- `EventLog.from_events(events)` – Builds a log from an iterable of `GameEvent` instances.

Persisted events include all metadata (timestamp/type/payload/visibility/audience).

## Game State Snapshots

`persistence.GameStateSnapshot` converts a `GameState` (including event log) into a serialisable payload.

```python
from avalon.persistence import snapshot_game_state, restore_game_state

snapshot = snapshot_game_state(game_state)
snapshot.save("game-state.json")

loaded = GameStateSnapshot.load("game-state.json")
restored_state = restore_game_state(loaded)
```

### Snapshot Contents

The payload includes:

- Configuration (`GameConfig` fields).
- Player roster with ids, display names, and roles.
- Current phase, round, attempt, scores, leader index, and team selection.
- Vote and mission history, including hidden mission actions.
- Assassination record (if resolved).
- RNG seed encoded during setup.
- Event log as a list of dictionaries.

Snapshots round-trip into fully functional `GameState` instances with all history intact.

### Use Cases

- **Pause/Resume**: Save during live play and resume later.
- **Testing**: Generate fixtures for integration tests or reproduction of bug scenarios.
- **Datasets**: Capture final states for agent training or strategy analysis.

## Interaction Transcript

While not part of the snapshot, the CLI transcript uses similar visibility semantics. Each `InteractionLogEntry` includes `visibility` and `audience`, and helper methods (documented in [`cli.md`](cli.md)) mirror the event filtering API.

## Recommended Workflows

1. **During Play** – Attach an `EventLog` to `GameState` (the CLI does this automatically) and optionally snapshot between rounds.
2. **After Play** – Serialise the event log (`to_jsonl`) and snapshot (`to_json`) for archival.
3. **Analysis** – Use `events_for_player` / `transcript_for_player` to reconstruct a player's experience without leaking hidden information.

## Testing

Unit tests in `tests/test_persistence.py` and `tests/test_events.py` verify snapshot round-trips, event serialisation, and filtering semantics. Use these as references when extending the schema.
