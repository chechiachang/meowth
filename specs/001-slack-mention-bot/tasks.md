# Tasks: Slack Mention Bot

**Input**: Design documents from `/specs/001-slack-mention-bot/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Tests are REQUIRED per constitution Test-First Development principle

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/meowth/`, `tests/` at repository root
- Paths based on plan.md structure

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [x] T001 Initialize Python project with pyproject.toml and uv.lock
- [x] T002 [P] Create project directory structure per plan.md in src/meowth/
- [x] T003 [P] Create test directory structure in tests/
- [x] T004 [P] Configure linting tools (flake8, black, mypy) with pyproject.toml
- [x] T005 [P] Create src/meowth/__init__.py
- [x] T006 [P] Create tests/__init__.py and test fixtures directory

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T007 Create environment configuration module in src/meowth/utils/config.py
- [x] T008 Create structured logging module in src/meowth/utils/logging.py
- [x] T009 [P] Create data model classes for Bot Instance in src/meowth/models.py
- [x] T010 [P] Create data model classes for Mention Event in src/meowth/models.py
- [x] T011 [P] Create data model classes for Response Message in src/meowth/models.py
- [x] T012 Create Slack client wrapper with reconnection logic in src/meowth/client.py
- [x] T013 Create test fixtures for Slack events in tests/fixtures/slack_events.py
- [x] T014 Setup main entry point with dependency injection in src/meowth/main.py

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Basic Mention Response (Priority: P1) 🎯 MVP

**Goal**: Enable bot to receive @meowth mentions and respond with "Meowth, that's right!"

**Independent Test**: Mention @meowth in Slack channel and receive correct response within 5 seconds

### Tests for User Story 1 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T015 [P] [US1] Unit test for mention event validation in tests/unit/test_mention_handler.py
- [x] T016 [P] [US1] Unit test for response message creation in tests/unit/test_mention_handler.py
- [x] T017 [P] [US1] Integration test for end-to-end mention handling in tests/integration/test_bot_integration.py
- [x] T018 [P] [US1] Unit test for sequential processing behavior in tests/unit/test_mention_handler.py

### Implementation for User Story 1

- [x] T019 [US1] Implement mention event handler in src/meowth/handlers/mention.py
- [x] T020 [US1] Implement bot application with event routing in src/meowth/bot.py
- [x] T021 [US1] Add mention response logic with exact text validation
- [x] T022 [US1] Add operational logging for mention events and responses
- [x] T023 [US1] Integrate mention handler with Slack client in bot.py

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently

---

## Phase 4: User Story 2 - Multi-Channel Support (Priority: P2)

**Goal**: Ensure bot works across all channels where it's invited

**Independent Test**: Invite bot to multiple channels and verify mention responses work in each channel independently

### Tests for User Story 2 ⚠️

- [x] T024 [P] [US2] Unit test for multi-channel event processing in tests/unit/test_mention_handler.py
- [x] T025 [P] [US2] Integration test for cross-channel functionality in tests/integration/test_bot_integration.py
- [x] T026 [P] [US2] Unit test for graceful channel removal handling in tests/unit/test_mention_handler.py

### Implementation for User Story 2

- [x] T027 [US2] Enhance mention handler to track channel context in src/meowth/handlers/mention.py
- [x] T028 [US2] Add channel-specific logging and error handling
- [x] T029 [US2] Implement graceful handling for removed channel access
- [x] T030 [US2] Add channel validation to response message creation

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently

---

## Phase 5: User Story 3 - Error Resilience (Priority: P3)

**Goal**: Handle Slack API errors gracefully with automatic recovery

**Independent Test**: Simulate API failures and verify bot recovers without crashing

### Tests for User Story 3 ⚠️

- [x] T031 [P] [US3] Unit test for API error handling in tests/unit/test_client.py
- [x] T032 [P] [US3] Unit test for exponential backoff reconnection in tests/unit/test_client.py
- [x] T033 [P] [US3] Integration test for connection recovery scenarios in tests/integration/test_bot_integration.py
- [x] T034 [P] [US3] Unit test for rate limit handling in tests/unit/test_client.py

### Implementation for User Story 3

- [x] T035 [US3] Implement exponential backoff reconnection logic in src/meowth/client.py
- [x] T036 [US3] Add comprehensive error categorization (retryable vs non-retryable)
- [x] T037 [US3] Implement rate limit respect and backoff handling
- [x] T038 [US3] Add connection status monitoring and health checks
- [x] T039 [US3] Enhance operational logging for error scenarios and recovery

**Checkpoint**: All user stories should now be independently functional

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [x] T040 [P] Add comprehensive type hints across all modules
- [x] T041 [P] Add docstrings for all public interfaces
- [x] T042 Add application health check endpoint for monitoring
- [x] T043 [P] Validate quickstart.md setup and deployment instructions
- [x] T044 Add graceful shutdown handling for production deployment
- [x] T045 [P] Add performance monitoring and metrics collection
- [x] T046 Run final code quality checks (flake8, black, mypy)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3)
- **Polish (Final Phase)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - May enhance US1 but should be independently testable
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - Enhances reliability of US1/US2 but should be independently testable

### Within Each User Story

- Tests MUST be written and FAIL before implementation (TDD requirement)
- Data models before business logic
- Core functionality before error handling
- Individual features before integration
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tasks marked [P] can run in parallel (within Phase 2)
- Once Foundational phase completes, all user stories can start in parallel (if team capacity allows)
- All tests for a user story marked [P] can run in parallel
- Data models marked [P] can run in parallel
- Different user stories can be worked on in parallel by different team members

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
Task: "Unit test for mention event validation in tests/unit/test_mention_handler.py"
Task: "Unit test for response message creation in tests/unit/test_mention_handler.py"
Task: "Integration test for end-to-end mention handling in tests/integration/test_bot_integration.py"

# Launch foundational data models together:
Task: "Create data model classes for Bot Instance in src/meowth/models.py"
Task: "Create data model classes for Mention Event in src/meowth/models.py"
Task: "Create data model classes for Response Message in src/meowth/models.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Test User Story 1 independently with real Slack workspace
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (MVP!)
3. Add User Story 2 → Test independently → Deploy/Demo  
4. Add User Story 3 → Test independently → Deploy/Demo
5. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (Core mention response)
   - Developer B: User Story 2 (Multi-channel support)
   - Developer C: User Story 3 (Error resilience)
3. Stories complete and integrate independently

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- TDD mandatory: Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Test with real Slack workspace at each checkpoint
- Use uv run for all Python execution and testing