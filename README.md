# Avalon

Avalon is a Python implementation of the Resistance: Avalon board game. The project currently focuses on building the core game engine with future hooks for LLM-driven agents.

## Development Setup

1. Install Poetry if it is not already available: `pipx install poetry` or follow the installation guide at [https://python-poetry.org/docs/](https://python-poetry.org/docs/).
2. Install project dependencies: `poetry install`.
3. Run formatting and linting: `poetry run ruff check .` and `poetry run ruff format .`.
4. Run static type checks: `poetry run mypy src`.
5. Execute tests: `poetry run pytest`.

## Repository Structure

```
.
├── pyproject.toml
├── README.md
├── src/
│   └── avalon/
│       └── __init__.py
└── tests/
```

## Implemented Domain Layer

- Enumerations for alignments and role types (`avalon.enums`).
- Role registry with default distributions, validation, and helpers (`avalon.roles`).
- Player model with agent hook placeholder and metadata accessors (`avalon.players`).
- Knowledge packet generator for setup vision (`avalon.knowledge`).
- Mission and game configuration models with official rule validation (`avalon.config`).
- Setup orchestration producing role assignments, player objects, and knowledge briefings (`avalon.setup`).
- Game state finite-state machine covering team proposals, voting, mission resolution, auto-fail handling, and scoring (`avalon.game_state`).
- Unit tests covering configuration, setup, and comprehensive game state scenarios.

## Next Steps

- Implement the assassination phase and finalize endgame resolution rules.
- Layer on interaction surfaces (CLI and agent adapters) using the new state machine primitives.
- Add structured event logging for future agent memory integration.
