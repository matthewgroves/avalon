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
- [x] **Dialogue Logging Hooks**
	- Record every prompt, hidden prompt, and system output into a structured transcript returned with the game state for downstream agent memory work.
- [x] **Private Role Briefings**
	- Deliver per-player role/knowledge briefings post-setup using transcript visibility tags to maintain secrecy.

### Phase 7: Persistence & Memory Hooks
- [x] Design event schema and implement append-only logger.
- [x] Add save/load serialization for `game_state` and replay capability.
- [x] Expose APIs for agents to query past events, with filters for public vs private visibility.

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

### Phase 10: LLM Agent Player Foundation ✅
- [x] **Player Type Designation** ✅
	- Extend `PlayerRegistration` to include player type (human vs agent).
	- Update config loader to parse agent designations from YAML.
	- Update CLI prompts to ask for player type during interactive setup.
	- Store player type in `Player` model for runtime access.
	- Add comprehensive tests for player type flows.
- [x] **Agent Interface Abstraction** ✅
	- Define protocol/interface for agent decision-making operations (propose team, vote, mission decision, assassination guess).
	- Create observation state objects containing game context visible to each player.
	- Design action schema for agent responses (structured output format).
- [x] **Google AI Studio Integration** ✅
	- Add google-generativeai dependency for Gemini API access.
	- Create LLM client wrapper handling API authentication via environment variable.
	- Implement prompt construction utilities for game state serialization.
	- Add response parsing with validation and error recovery.
	- Configure for Gemini 2.0 Flash model.
- [x] **Unit Tests** ✅
	- Test player type registration and serialization.
	- Mock LLM client for deterministic agent behavior testing.
	- Validate observation state construction for different game phases.
	- Test action parsing with valid/invalid LLM responses.

### Phase 11: Agent Decision Integration ✅
- [x] **Team Proposal Agent Logic** ✅
	- Construct prompts with current game state, visible players, mission requirements.
	- Parse team selection responses into player ID lists.
	- Handle invalid responses (wrong count, unknown players, malformed output).
- [x] **Voting Agent Logic** ✅
	- Present proposed team and game context to agents.
	- Parse approve/reject decisions from LLM responses.
	- Support reasoning/explanation capture for transparency.
- [x] **Mission Execution Agent Logic** ✅
	- Provide mission context to agents on selected teams.
	- Parse success/fail decisions respecting alignment constraints.
	- Validate resistance agents cannot submit fail cards.
- [x] **Assassination Agent Logic** ✅
	- Present final game state to assassin agents.
	- Parse Merlin identification guess.
	- Handle invalid target selections.
- [x] **Integration Tests** ✅
	- Run full games with all-agent players using mocked LLM responses.
	- Validate phase transitions work correctly with agent decisions.
	- Test mixed human/agent games.

### Phase 12: Agent Communication & Discussion
- [x] **Discussion Data Model** ✅
	- [x] Create `DiscussionStatement` dataclass capturing speaker, message, timestamp, round/phase context.
	- [x] Add `DiscussionRound` dataclass for structured turn-taking and statement tracking.
	- [x] Extend `GameState` to track discussion history per phase.
	- [x] Add discussion statements to `AgentObservation` for context in decision-making.
- [ ] **Discussion Configuration**
	- [ ] Add `DiscussionConfig` dataclass defining when discussions occur and turn limits.
	- [ ] Define discussion opportunities: PRE_PROPOSAL, PRE_VOTE, POST_MISSION_RESULT, PRE_ASSASSINATION.
	- [ ] Configure max statements per player per discussion phase.
	- [ ] Add option to enable/disable discussions in `GameConfig`.
- [ ] **Discussion Phase Logic**
	- [ ] Implement discussion turn manager handling speaking order (round-robin or leader-first).
	- [ ] Add validation for discussion timing (only during configured phases).
	- [ ] Track which players have spoken in current discussion round.
	- [ ] Implement discussion timeout/turn limit enforcement.
- [ ] **Human Player Discussion Interface**
	- [ ] Add CLI prompt allowing human players to make statements during discussion.
	- [ ] Support optional participation (players can skip/pass their turn).
	- [ ] Display all statements to all players in real-time.
	- [ ] Show discussion history at appropriate game points.
- [ ] **Agent Discussion Interface**
	- [ ] Add `make_statement()` method to agent interface/LLM client.
	- [ ] Create discussion prompts including game context, recent events, and prior statements.
	- [ ] Parse agent-generated discussion statements with validation.
	- [ ] Include discussion history in observation state for informed responses.
- [ ] **Strategic Discussion Prompting**
	- [ ] Design prompts encouraging role-appropriate behavior (Merlin subtlety, evil misdirection).
	- [ ] Provide context on what just happened (mission result, vote pattern, proposal).
	- [ ] Suggest discussion topics: suspicions, defenses, voting rationale, team justifications.
	- [ ] Add examples of good vs poor discussion for each role type.
- [ ] **Discussion Flow Integration**
	- [ ] Insert discussion phase before team proposals (leader explains intentions).
	- [ ] Insert discussion phase before votes (debate proposed team).
	- [ ] Insert discussion phase after mission results (analyze what happened).
	- [ ] Insert discussion phase before assassination (final accusations/defenses).
	- [ ] Ensure smooth transitions between discussion and action phases.
- [ ] **Event Logging & Persistence**
	- [ ] Add `DISCUSSION_STATEMENT` event type to event log.
	- [ ] Record all statements with player ID, timestamp, and game context.
	- [ ] Mark all discussion as public visibility (accessible to all players).
	- [ ] Include discussion transcript in interaction log.
- [ ] **Testing & Validation**
	- [ ] Unit tests for discussion data models and turn management.
	- [ ] Test human-only discussion flows in CLI.
	- [ ] Test agent-only discussion with mocked LLM responses.
	- [ ] Test mixed human/agent discussions.
	- [ ] Validate discussion history properly surfaces in observations.
	- [ ] Test skip/pass functionality for optional participation.
	- [ ] Integration tests with full game including all discussion phases.

### Phase 13: Agent Memory & Strategy ✅
- [x] **Multi-LLM Provider Support** ✅
	- Implemented OpenAI client for GPT-5 Nano with reasoning model support.
	- Implemented OpenRouter client for access to multiple open-source models.
	- All clients inherit from BaseLLMClient protocol with consistent interface.
	- Support for model-specific parameters (reasoning_effort, max_completion_tokens).
- [x] **Prompt Engineering & Quality Improvements** ✅
	- Enhanced knowledge display to explicitly state "These players are EVIL" for Merlin.
	- Added clear player identity confirmation to prevent confusion.
	- Implemented deduction examples for Loyal Servants to learn from mission failures.
	- Added role-specific strategic guidance for all roles.
	- Improved JSON parsing to handle explanatory text before/after JSON blocks.
- [x] **"private_reasoning" → "true_reasoning" Terminology** ✅
	- Renamed all prompt references from "private_reasoning" to "true_reasoning".
	- Fixed OpenAI safety guardrail issue that was blocking genuine strategic reasoning.
	- Maintained backward compatibility with existing dataclass field names.
- [x] **Bug Fixes** ✅
	- Fixed critical Merlin knowledge bug caused by double `perform_setup()` calls.
	- Added `setup` parameter to `run_interactive_game()` to prevent role mismatches.
	- Updated all game runners to pass pre-computed setup objects.
- [x] **Project Cleanup** ✅
	- Removed obsolete test/debug scripts (test_openai.py, test_merlin_knowledge.py, etc.).
	- Cleaned up old backup files (llm_client_old.py).
	- Updated README with current game runner examples.
- [x] **Testing & Validation** ✅
	- All 97 tests passing after prompt improvements.
	- Verified agent decision quality dramatically improved.
	- Agents now properly use role knowledge and deduce from patterns.

## 6. Next Steps
1. **In Progress**: Phase 12 - Add discussion/communication layer for richer agent interactions.
2. Implement agent memory system to track conversation history and patterns.
3. Add observability tools for analyzing agent decision quality.
4. Experiment with different models and prompt strategies for optimal play.
5. Consider adding optional Lady of the Lake mechanic.
6. Explore multi-turn strategic planning for agents.

