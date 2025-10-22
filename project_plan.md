# Avalon Project Plan

## 1. Objectives and Constraints
- Build a faithful Python implementation of The Resistance: Avalon using official rules and role set.
- Support both human and future LLM-driven agents with extensible interaction interfaces.
- Record structured state transitions and player actions for downstream personalization and memory experiments.
- Maintain separation between hidden and public information while allowing controlled disclosures to agents.
- Deliver test coverage for setup, mission flow, voting mechanics, and win conditions.

## 2. Rules Baseline
- Player counts: 5-10, with corresponding mission team sizes and number of fails required (two fails for mission 4 in 7+ player games).
- Default roles: Merlin, Assassin, Percival, Morgana, Mordred, Oberon as per official distribution; allow optional toggles but default to official recommendations.
- Phases: role assignment and knowledge reveal, leadership rotation per round, team proposal, voting, mission execution, outcome reveal, potential assassination.
- Victory: Resistance wins three missions or survives assassination (Merlin hidden); Minions win after three failed missions or successful Merlin assassination.
- Track Lady of the Lake token (optional official module) but include configuration flag to enable later.

## 3. System Architecture
### 3.1 Core Modules
- `roles`: dataclasses/enums for role metadata (alignment, knowledge visibility, special powers).
- `players`: player models with identity, role, visible info, history logs, agent hooks.
- `missions`: mission setup, proposal validation, voting, execution, result recording.
- `game_state`: master state object capturing current round, leader index, score tally, history, and configuration.
- `events`: immutable event records for logging and replay.

### 3.2 Rule Engine & Phase Controller
- Finite state machine managing transitions: Setup → Leadership → TeamProposal → TeamVote → MissionExecution → Outcome → Assassination → Endgame.
- Validation layer to enforce official rules (team sizes, vote counting, mission fail thresholds).
- Randomness utilities for role assignment and deck draws with deterministic seeding option for testing.

### 3.3 Interaction Layer
- CLI driver for human players using prompts and concealed inputs where necessary (e.g., voting, mission cards).
- Agent interface abstraction exposing observation snapshots and accepted action schemas (vote, select team, mission choice).
- Memory hooks providing agents with event feeds and private notes without leaking hidden information to others.

### 3.4 Persistence & Logging
- Structured event log (JSONL or similar) capturing timestamped actions, votes, mission outcomes, and public chat.
- Save/load serialization of `game_state` for pause/resume and agent training datasets.

## 4. Implementation Phases
### Phase 0: Repository Foundations
- Initialize Python packaging (e.g., `pyproject.toml` with Poetry or Hatch; decide on dependency manager).
- Set up tooling: type checking (mypy), linting (ruff), testing (pytest), formatting (black or ruff formatter).
- Configure CI workflow for lint and test.

### Phase 1: Domain Modeling
- [x] **Alignment & Role Foundations**
	- Implement `Alignment` enum (`RESISTANCE`, `MINION`).
	- Implement `RoleType` enum covering official Avalon roles.
	- Create `RoleDefinition` dataclass capturing alignment, visibility rules, assassination eligibility, and special tags (Merlin, Assassin, etc.).
	- Encode official role metadata in a central registry with helper selectors (e.g., default role sets per player count).
- [x] **Knowledge & Visibility Rules**
	- Define structures describing which roles each role sees at setup (Merlin vision, Percival ambiguity, evil mutual knowledge with Oberon exception).
	- Provide functions to compute knowledge packets for a given player roster.
- [x] **Player Model**
	- Implement `Player` dataclass with immutable identity fields (id, display_name), role assignment, alignment-derived helpers, and history placeholders for future use (public_log_ids, private_notes keys).
	- Include agent hook placeholder (callable or protocol) without implementing agent logic yet.
- [x] **Configuration Objects**
	- Implement `MissionConfig` data describing team sizes and fail thresholds per round for player counts 5-10.
	- Implement `RoleConfig`/`GameConfig` capturing enabled roles, optional modules (Lady of the Lake flag), deterministic seed, and validation helpers ensuring compatibility with player count.
- [x] **Validation Utilities**
	- Add functions validating that selected roles satisfy official requirements (e.g., Merlin paired with Assassin, Percival with Merlin, minimum evil count).
	- Include exception types for configuration errors.
- [x] **Unit Tests**
	- Test role registry metadata (alignments, visibility, assassination eligibility).
	- Test knowledge generation for canonical setups (5-player default, 10-player with full evil cast).
	- Test mission configuration tables against official rulebook.

### Phase 2: Game Setup Logic
- [x] **Input Validation & Seeding**
	- Accept ordered player registrations (names and optional ids) matching `GameConfig.player_count`.
	- Validate uniqueness of player identifiers and non-empty names.
	- Initialize deterministic RNG using explicit seed parameter or `GameConfig.random_seed` fallback.
- [x] **Role Assignment**
	- Shuffle configured roles with RNG and bind each to a player seat.
	- Expose assignment data via immutable structures for downstream phases.
- [x] **Player Construction**
	- Instantiate `Player` objects with generated ids, display names, assigned roles, and default history placeholders.
- [x] **Knowledge Distribution**
	- Reuse `compute_setup_knowledge` to build per-player `KnowledgePacket`s.
	- Package results into structured briefings intended for private delivery.
- [x] **Setup Summary Artifact**
	- Create dataclasses capturing the finalized lobby (public player list), role assignments, and knowledge map.
	- Provide helper to produce public lobby snapshot (names only) for display/UI consumption.
- [x] **Unit Tests**
	- Validate deterministic role assignment with fixed seed.
	- Ensure knowledge packets align with assigned roles in canonical scenarios.
	- Confirm validation errors trigger on incorrect player counts or duplicate registrations.

### Phase 3: Turn & Phase Management
- Build finite state machine to manage phases with explicit transition methods.
- Implement leader rotation, team nomination handling, validation of team sizes, and nomination history storage.
- Add voting system: collect secret votes, reveal aggregated outcome, track consecutive rejections (ending at 5).

### Phase 4: Mission Execution
- Implement mission success/fail card submissions with alignment-based rules (minions may fail, resistance must succeed).
- Handle special cases: mission 4 requiring two fails in 7+ player games; Oberon knowledge handling.
- Update mission history, success/failure scoreboard, and check for win thresholds after each mission.

### Phase 5: Assassination & Endgame
- Trigger assassination phase when resistance reaches three successes and assassin role exists.
- Implement assassin selection logic, reveal outcome, determine final winner, and record event.
- Handle immediate evil victory when three missions fail or fifth team rejection occurs.

### Phase 6: Interaction Layer MVP
- Create CLI interface supporting human input with privacy management (e.g., hidden prompts for votes, mission choices).
- Implement mock agent stubs that follow simple scripted logic for automated tests.
- Provide logging of public dialogue placeholders and private notes for future LLM integration.

### Phase 7: Persistence & Memory Hooks
- Design event schema and implement append-only logger.
- Add save/load serialization for `game_state` and replay capability.
- Expose APIs for agents to query past events, with filters for public vs private visibility.

### Phase 8: Testing & Validation
- Write unit tests for role distribution, knowledge reveals, mission configuration per player count.
- Add integration tests simulating full games with deterministic seeds covering edge cases (e.g., multiple rejected teams, assassination outcomes).
- Validate CLI flows via snapshot or Golden tests where feasible.

### Phase 9: Documentation & Developer Experience
- Produce README with setup instructions, rule summary, and CLI usage.
- Add architecture notes detailing module responsibilities and extension points for LLM agents.
- Document agent API contracts and memory interfaces for future AI integration.

## 5. Risk Mitigation & Stretch Goals
- Hidden information leaks: enforce strict access controls in data structures; add unit tests verifying agents only see allowed fields.
- Concurrency between multiple agents: plan for turn-based message queue abstraction if expanding beyond single-thread CLI.
- Stretch goals: web/socket-based UI, pluggable LLM agent management service, analytics dashboard for mission history.

## 6. Next Steps
1. Decide on dependency management tool (Poetry vs Hatch vs setuptools).
2. Scaffold Python package structure and tooling configs (Phase 0 tasks).
3. Begin implementing domain models (Phase 1) with comprehensive tests.
