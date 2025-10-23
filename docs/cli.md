# Interactive CLI Guide

The `avalon.interaction` module provides a prompt-driven interface for running full Avalon games in the terminal. This guide covers prerequisites, execution steps, and the structure of the interaction transcript exposed after each run.

## Prerequisites

- Python environment managed by Poetry (see `README.md` for installation steps).
- Project dependencies installed via `poetry install`.

## Launching the CLI

Use the module entry point to start a game:

```bash
poetry run python -m avalon.interaction
```

You will be prompted for:

1. **Player count** – Default is 5 (accept with Enter). Valid range is 5–10.
2. **Player names** – Enter a non-empty display name for each seat.
3. **Game actions** – The CLI guides proposals, votes, mission cards, and the assassination.

Sensitive prompts (votes, mission cards, assassin guess) use hidden input via `getpass` so responses are not echoed to the terminal.

### Private Briefing Delivery

After setup the CLI delivers each player's role and knowledge packet using transcript visibility tags. The default behaviour is sequential: the moderator invites each player to the screen, the briefing prints privately, and the transcript records an audience tag of `player:{player_id}`.

`run_interactive_game` accepts a `BriefingOptions` object to tailor the delivery:

- `mode` – `BriefingDeliveryMode.SEQUENTIAL` (default) or `BriefingDeliveryMode.BATCH`. Batch delivery prints every briefing at once for moderators to relay manually.
- `pause_before_each` – When `True`, the CLI issues a hidden prompt asking the addressed player to confirm they are ready before revealing their briefing.
- `pause_after_each` – When `True`, players acknowledge once they finish reading so the moderator can clear the screen before the next briefing.

Example:

```python
from avalon.config import GameConfig
from avalon.interaction import BriefingOptions, BriefingDeliveryMode, run_interactive_game

config = GameConfig.default(7)
options = BriefingOptions(
    mode=BriefingDeliveryMode.SEQUENTIAL,
    pause_before_each=True,
    pause_after_each=True,
)

run_interactive_game(config, briefing_options=options)
```

The transcript captures all additional prompts, making it easy to audit who received which messages.

## Transcript Logging

`run_interactive_game` returns an `InteractionResult` containing:

- `state`: the final `GameState`.
- `transcript`: a tuple of `InteractionLogEntry` items capturing every prompt or message.

Each entry records:

| Field | Description |
| --- | --- |
| `event` | `PROMPT`, `HIDDEN_PROMPT`, or `OUTPUT` |
| `message` | Prompt text or printed output |
| `response` | Player response (where applicable) |
| `visibility` | `PUBLIC` or `PRIVATE` |
| `audience` | Tuple of audience tags authorised to see the entry |

### Visibility Helpers

`InteractionResult` exposes convenience methods for filtered transcripts:

- `public_transcript()` – Returns only public entries.
- `transcript_for_player(player_id)` – Returns entries visible to a specific player (public + their private prompts).
- `transcript_for_alignment(alignment)` – Returns entries visible to players of a given alignment (`Alignment.RESISTANCE` or `Alignment.MINION`).

Private prompts sent to individual players include an audience tag in the form `player:{player_id}`. Alignment-scoped outputs (for future interfaces) use tags like `alignment:RESISTANCE`.

### Example Usage

```python
from avalon.config import GameConfig
from avalon.interaction import run_interactive_game

config = GameConfig.default(5)
result = run_interactive_game(config)

public_entries = result.public_transcript()
player_view = result.transcript_for_player("player_1")
```

## Custom Interaction Backends

To integrate the engine with other interfaces (e.g., chat app, web UI, agent harness), implement the `InteractionIO` protocol:

```python
from dataclasses import dataclass
from avalon.interaction import InteractionIO

@dataclass
class CustomIO(InteractionIO):
    def read(self, prompt: str) -> str:
        # Render prompt and return response
        ...

    def read_hidden(self, prompt: str) -> str:
        # Collect secret input for votes/mission cards
        ...

    def write(self, message: str) -> None:
        # Display output to the user(s)
        ...
```

Pass your implementation to `run_interactive_game(config, io=CustomIO(...))`.

## Scripted Runs for Testing

`tests/test_interaction.py` demonstrates a scripted harness (`ScriptedIO`) that feeds predetermined responses and captures outputs for assertion. Use this pattern to build reproducible simulations or integrate agents that require deterministic interactions.
