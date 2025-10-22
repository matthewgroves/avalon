# Avalon Project Overview

Avalon is a Python implementation of *The Resistance: Avalon* designed for experimentation with human and AI agents. The codebase emphasises strict rules fidelity, structured logging, and clear separation between public and hidden information. This document summarises the game engine, the major components, and the artefacts it produces.

## Core Goals

- **Rules-accurate engine** – Recreate the official Avalon ruleset with deterministic testing hooks.
- **Agent-friendly design** – Provide clear data structures, visibility controls, and logging for learning agents.
- **Observability** – Capture events, transcripts, and persistent snapshots for replay and analysis.
- **Extensibility** – Organise modules so new interfaces (CLI, web, agent harnesses) can layer on top of the engine.

## High-Level Architecture

```text
src/avalon/
├── config.py          # Mission/role configuration tables and validation
├── enums.py           # Alignment / role / phase enums
├── events.py          # Structured game event log with visibility tagging
├── game_state.py      # Core finite-state machine for missions, voting, scoring
├── interaction.py     # Prompt-driven CLI + transcript logging helpers
├── knowledge.py       # Setup knowledge packets for each role
├── persistence.py     # Snapshot (save/load) utilities for GameState + events
├── players.py         # Player dataclass and agent hook placeholder
├── roles.py           # Official Avalon role definitions and helpers
├── setup.py           # Lobby registration, role assignment, knowledge briefings
└── __init__.py        # Public package exports
```

Key ideas:

- **Finite-state engine** – `GameState` manages phase transitions, validates actions, records votes/missions, and emits `GameEvent` records for downstream consumers.
- **Structured logging** – `events.EventLog` stores timestamped events with visibility metadata, while `interaction` records a transcript of prompts and responses using the same concepts.
- **Persistence** – `persistence.GameStateSnapshot` captures the entire state (including event logs) for pause/resume workflows.
- **Visibility-aware data** – Both event and transcript entries include audience tags so agents receive only the information they are entitled to.

## Produced Artefacts

| Artefact | Source | Format | Purpose |
| --- | --- | --- | --- |
| **GameEvent log** | `GameState.event_log` | JSONL / in-memory | Replay state transitions, feed agent memory, analytics |
| **Interaction transcript** | `InteractionResult.transcript` | In-memory tuple of `InteractionLogEntry` | Reconstruct CLI prompts, filter by player/alignment |
| **GameState snapshot** | `snapshot_game_state()` | JSON (via `GameStateSnapshot`) | Save/resume games, deterministic testing |
| **Setup knowledge** | `perform_setup()` | Mapping of player id → `KnowledgePacket` | Guide agent briefings without leaking hidden info |

## Key Flows

1. **Setup** – `perform_setup` validates registrations, assigns roles with deterministic RNG, and constructs players plus knowledge packets. The returned `SetupResult` seeds `GameState`.
2. **Game loop** – `interaction.run_interactive_game` drives the CLI, updating `GameState` until victory. Actions emit events and append to the transcript with audience tags.
3. **Logging & persistence** – At any point you can snapshot the state (`snapshot_game_state`) or serialise the event log via `EventLog.to_jsonl()`.
4. **Replay & analysis** – Load a saved JSON snapshot (`GameStateSnapshot.load`) and inspect public/private views of events and transcripts for agent training or debugging.

## Next Steps

- Review the detailed guides in this `docs/` directory:
  - [`cli.md`](cli.md) – Running the interactive CLI and understanding the transcript.
  - [`events-and-persistence.md`](events-and-persistence.md) – Event schema, visibility, and save/load examples.
  - [`development.md`](development.md) – Environment setup, tooling, and contribution workflow.

For a lightweight introduction see the top-level [`README.md`](../README.md). For granular implementation detail, browse the module docstrings and unit tests under `tests/`.
