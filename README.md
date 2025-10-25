# Avalon

# Avalon

**LLM-driven agent players powered by OpenAI's GPT-5 models**

The Resistance: Avalon implemented in Python with full rules support, designed for **tabletop play** (humans passing a laptop around), automated testing, and LLM-agent simulations.

## Features

- Official Avalon rules with special role support (Merlin, Percival, Morgana, Mordred, Oberon)
- Fully automated game state machine (team proposals, votes, missions, assassination)
- Mixed human and LLM agent players
- Interactive CLI for tabletop play with hidden prompts for secrets
- YAML configuration for scripted/automated games
- Comprehensive test suite for rules validation
- Event logging and game state persistence
- OpenAI integration with automatic prompt caching for cost optimization

## Quick Start

### Installation

```bash
# Clone the repository
git clone <your-repo-url>
cd avalon

# Install dependencies using Poetry
poetry install
```

### Get an OpenAI API Key

1. Visit [OpenAI API Keys](https://platform.openai.com/api-keys)
2. Generate an API key
3. Set the environment variable:

```bash
export OPENAI_API_KEY="your-api-key-here"
```

### Run Your First Game

```bash
# Run a game with agent players
poetry run python run_openai_game.py config-test-openai.yaml

## Features

- **Complete Avalon Game Engine**: Team proposals, voting, missions, assassination, all special roles
- **LLM Agent Players**: AI agents powered by OpenAI GPT-5 models that can play strategically
- **Mixed Games**: Seamlessly combine human and agent players
- **YAML Configuration**: Configure games via config files
- **Interactive CLI**: Play via console with hidden prompts for secret decisions
- **Comprehensive Testing**: 97+ tests covering all game mechanics
- **Automatic Prompt Caching**: Cost optimization through OpenAI's built-in prompt caching

## Quick Start

### Prerequisites

1. Install Poetry: `pipx install poetry` or follow [Poetry installation guide](https://python-poetry.org/docs/)
2. Install dependencies: `poetry install`

### Play a Human-Only Game

```bash
poetry run python -m avalon.interaction
```

The CLI will prompt for player count, optional roles, and player names.

### Play with Agent Players

1. Set your OpenAI API key:
   ```bash
   export OPENAI_API_KEY="your-api-key-here"
   ```
2. Run with a config file:
   ```bash
   poetry run python run_openai_game.py config-test-openai.yaml
   ```

Agents will automatically make decisions with reasoning displayed in the CLI.

## Agent Players

Agent players use OpenAI's GPT-5 models to:
- **Propose teams** as mission leaders
- **Vote** on team proposals with strategic reasoning
- **Execute missions** (playing success or fail cards based on alignment)
- **Guess Merlin** in the assassination phase

### How It Works

1. **Observation Building**: Each agent receives filtered game state including:
   - Their role and alignment
   - Role-based knowledge (e.g., Merlin sees evil players)
   - Public game history (votes, mission results)
   - Current phase and mission requirements

2. **LLM Decision-Making**: The agent's observation is serialized into a natural language prompt, sent to OpenAI, and the structured JSON response is parsed into game actions.

3. **Validation & Fallback**: Invalid agent responses trigger fallback behaviors or human intervention.

### Configuration

Players can be specified in two formats:

**Simple format** (defaults to human):
```yaml
players:
  - Alice
  - Bob
```

**Structured format** (specify type):
```yaml
players:
  - name: Alice
    type: human
  - name: BobBot
    type: agent
```

## Development

### Running Tests

```bash
poetry run pytest                    # Run all tests
poetry run pytest tests/test_agents.py -v  # Run agent tests
```

### Code Quality

```bash
poetry run ruff check .              # Linting
poetry run ruff format .             # Formatting
poetry run mypy src                  # Type checking
```

### Pre-commit Hooks

Install pre-commit hooks for automatic checks:
```bash
poetry run pre-commit install
```

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
- Game state finite-state machine covering team proposals, voting, mission resolution, auto-fail handling, scoring, assassination workflow, and mission action/public summary logging (`avalon.game_state`).
- Unit tests covering configuration, setup, and comprehensive game state scenarios.
- Interaction utilities with a prompt-based CLI runner and scripted harness for automated validation (`avalon.interaction`).
- Custom role selection allowing users to choose which optional special characters (Percival, Morgana, Mordred, Oberon) to include, with remaining slots filled by generic servants/minions (`avalon.roles.build_role_list`).
- YAML configuration file support for fully automated game setup without interactive prompts (`avalon.config_loader`).
- Structured event logging primitives (`avalon.events`) captured during state transitions and major outcomes.
- Persistence helpers for snapshotting and restoring game state, including event logs (`avalon.persistence`).

## Interactive CLI

- Run `poetry run python -m avalon.interaction` to play a full game via the console.
- The CLI prompts for player count, optional special character selection, player names, and guides proposals, votes, mission cards, and assassination guesses.
- Alternatively, pass a config file with `poetry run python -m avalon.interaction --config config.yaml` to skip setup prompts and load all configuration from YAML.
- Sensitive decisions (votes and mission cards) are collected using hidden prompts to preserve secrecy at the table.
- Private setup briefings can be tailored via `BriefingOptions` (sequential vs batch, optional readiness/acknowledgement pauses).
- `run_interactive_game` returns an `InteractionResult` bundling the final `GameState` and a transcript of prompts/responses (`InteractionLogEntry`) categorized by `InteractionEventType` (prompt, hidden prompt, output).

## Architecture

### Core Modules

- **`avalon.enums`**: Alignments, role types, player types (HUMAN/AGENT)
- **`avalon.roles`**: Role definitions, validation, and distribution
- **`avalon.players`**: Player model with type designation
- **`avalon.knowledge`**: Setup vision/knowledge packets for each role
- **`avalon.config`**: Game configuration with official rule validation
- **`avalon.setup`**: Role assignment and player briefing generation
- **`avalon.game_state`**: FSM managing proposals, voting, missions, assassination
- **`avalon.interaction`**: CLI driver and prompt-based game runner
- **`avalon.config_loader`**: YAML configuration parser
- **`avalon.events`**: Event logging for game actions
- **`avalon.persistence`**: State snapshotting and restoration

### Agent System

- **`avalon.agents`**: Agent interfaces, observation state, action schemas
- **`avalon.openai_client`**: OpenAI API client with automatic prompt caching
- **`avalon.agent_manager`**: Coordinates LLM clients with agent players
- **`avalon.mock_llm_client`**: Mock client for deterministic testing

### Data Flow

```
Config/Setup → GameState → AgentManager → OpenAIClient → OpenAI API (GPT-5)
                   ↓
              Observation (filtered game state)
                   ↓
              Prompt Construction (auto-cached if >1024 tokens)
                   ↓
              LLM Response → Parsed Action
                   ↓
              Game State Update
```
                   ↓
              LLM Response → Parsed Action
                   ↓
              Game State Update
```

## Project Status

**Phase 10: LLM Agent Foundation** - Complete
  - Player type designation
  - Agent interfaces and observation state
  - OpenAI API integration with automatic prompt caching
  - Mock client for testing

**Phase 11: Agent Decision Integration** - Complete
  - Team proposal, voting, mission execution, assassination
  - Mixed human/agent game support
  - Full integration tests

**Phase 12: Communication & Discussion** - In Progress
  - Document transcript schemas and agent integration points covering visibility-filtered event feeds.
  - Thread event visibility metadata through interaction outputs to surface personalised historical views.
  - Multi-turn agent conversations
  - Strategic discussion phases
  
**Phase 13: Memory & Strategy** - Optional
  - Conversation history tracking
  - Advanced prompt engineering
  - Role-specific strategies

## Examples

### Running a Game

```bash
# Run a game with OpenAI GPT-5 models (recommended)
poetry run python run_openai_game.py config-test-openai.yaml
```

### Prompt Caching

OpenAI automatically caches prompts over 1024 tokens, reducing costs by 50% for cached tokens. No configuration required - it works automatically with the `OpenAIClient`.

Cache is valid for 5-10 minutes and automatically cleared within 1 hour. Perfect for game sessions with multiple agent decisions.

### Custom LLM Client

Implement the `LLMClient` protocol to use different LLM providers:

```python
from avalon.agents import AgentObservation, TeamProposal, VoteDecision
from avalon.agent_manager import LLMClient

class CustomLLMClient:
    def propose_team(self, observation: AgentObservation) -> TeamProposal:
        # Your custom logic here
        ...
    
    def vote_on_team(self, observation: AgentObservation) -> VoteDecision:
        ...
    
    # Implement execute_mission and guess_merlin
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Run the test suite and linters
5. Submit a pull request
