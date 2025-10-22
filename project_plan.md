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
- [x] **Phase & Outcome Modeling**
	- Introduce enums for game phases and mission outcomes.
	- Define vote and mission record dataclasses capturing round/attempt metadata and aggregate results.
- [x] **Game State Core**
	- Implement `GameState` with player roster, round tracking, leader index, mission/vote history, and scoreboard.
	- Compute assassin presence flag and provide lookup helpers for players by id.
- [x] **Team Proposal Flow**
	- Validate leader authority, enforce team sizes per mission, and prevent duplicate or invalid player selections.
	- Transition state to voting phase with stored proposal.
- [x] **Voting Mechanics**
	- Collect simultaneous votes, compute approval majority, persist vote records, and handle leader rotation.
	- Detect five consecutive rejections and auto-fail the mission per official rules.
- [x] **Mission Resolution**
	- Accept mission card submissions, enforce resistance success-only rule, and count fail cards against round-specific thresholds.
	- Update mission history, scoreboard, and determine success/failure outcomes.
- [x] **Round Advancement & Victory Detection**
	- Manage round resets, attempt counters, and leader rotation after each mission or auto-fail.
	- Detect win conditions (three successes or fails) and surface assassination pending state when applicable.
- [x] **Unit Tests**
	- Cover happy path approvals, rejections, auto-fail trigger, mission fail thresholds (including mission four), and victory transitions.
	- Verify invalid actions (wrong phase, wrong leader, duplicate players) raise appropriate errors.
### Phase 4: Mission Execution
- [x] **Mission Action Modeling**
	- Add lightweight dataclasses to capture individual mission card submissions while keeping them private to the engine.
	- Ensure stored actions remain detached from public state representations to avoid information leaks.
- [x] **Public Mission Summaries**
	- Provide sanitized mission summaries that reveal only aggregate information (result, fail counts, auto-fail status).
	- Expose helpers on `GameState` to access public mission history snapshots for UI/agent consumption.
- [x] **Mission Recording Enhancements**
	- Persist private mission actions alongside existing `MissionRecord` metadata for analytics and replay.
	- Randomize or obfuscate action ordering where necessary to preserve secrecy.
- [x] **Validation & Edge Cases**
	- Confirm mission four fail-threshold logic and auto-fail behaviors still operate with the new recording pipeline.
	- Extend error handling to surface clear diagnostics when submissions are malformed.
- [x] **Unit Tests**
	- Add focused tests covering the new public/private mission representations and failure scenarios.
	- Verify that sanitized summaries exclude identifying data while preserving statistical accuracy.

### Phase 5: Assassination & Endgame
- [x] **Assassination Trigger Conditions**
	- Resistance reaching three successes now pushes `GameState` into `ASSASSINATION_PENDING` when an assassin-tagged role exists, retaining provisional victory metadata.
- [x] **Assassin Action Interface**
	- `perform_assassination` validates assassin identity, accepts a Merlin guess, blocks duplicate resolutions, and rejects unknown targets.
- [x] **Outcome Resolution**
	- Assassination outcomes set the final winner and persist an `AssassinationRecord` for replay fidelity.
- [x] **Final State Guardrails**
	- `_ensure_phase` short-circuits further actions after `GAME_OVER`, covering assassination and post-game command attempts.
- [x] **Unit Tests**
	- Added scenarios for correct/incorrect guesses, invalid targets, single-resolution enforcement, and bypass cases for auto-fail or minion victories.

### Phase 6: Interaction Layer MVP
- [x] **Interaction IO Abstractions**
	- Define a shared prompt surface (`InteractionIO`) and console-backed implementation using hidden prompts for private decisions.
- [x] **CLI Game Runner**
	- Drive `GameState` transitions via user prompts, covering team proposals, voting, missions, and assassination flow.
- [x] **Scripted Test Harness**
	- Add deterministic scripted backend to exercise the CLI loop under test and ensure successful resistance outcomes.
- [ ] **Dialogue Logging Hooks**
	- Capture emitted prompts and responses into structured records for future agent memory integration.

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
