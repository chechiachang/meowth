# Tasks: Slack-Notion Integration

**Input**: Design documents from `/specs/001-slack-notion-integration/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Test tasks are NOT included as they were not explicitly requested in the feature specification.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure for Python 3.11+ Slack-Notion integration service

- [ ] T001 Create project structure with src/ and tests/ directories per implementation plan
- [ ] T002 Initialize Python project with uv package manager and create pyproject.toml with slack-sdk, notion-client, uvloop, pydantic, APScheduler dependencies
- [ ] T003 [P] Configure linting and formatting tools (flake8, black, mypy) in pyproject.toml
- [ ] T004 [P] Create .env.example file with required environment variables for Slack and Notion API credentials
- [ ] T005 [P] Setup basic logging configuration in src/config/logging.py
- [ ] T006 [P] Create Dockerfile and docker-compose.yml for containerized deployment

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T007 Create database schema and SQLAlchemy models foundation in src/models/__init__.py
- [ ] T008 [P] Implement configuration management with Pydantic settings in src/config/settings.py
- [ ] T009 [P] Setup database connection and session management in src/config/database.py
- [ ] T010 [P] Create base Slack client with socket mode setup in src/services/slack/client.py
- [ ] T011 [P] Create base Notion client with authentication in src/services/notion/client.py
- [ ] T012 [P] Implement rate limiting framework with token bucket algorithm in src/services/rate_limiter.py
- [ ] T013 [P] Setup processing queue infrastructure with AsyncIO in src/scheduling/queue.py
- [ ] T014 [P] Create error handling middleware and custom exceptions in src/services/exceptions.py
- [ ] T015 [P] Setup API routing framework with FastAPI in src/main.py
- [ ] T016 [P] Implement health check endpoint in src/services/health.py
- [ ] T017 Create CLI module structure in src/cli/__init__.py

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Slack Command to Notion Page Creation (Priority: P1) 🎯 MVP

**Goal**: Enable team members to create Notion pages via Slack slash commands (/create-notion [content])

**Independent Test**: Configure test Slack workspace and Notion database, send `/create-notion Test message`, verify page appears in Notion with correct metadata

### Implementation for User Story 1

- [ ] T018 [P] [US1] Create SlackMessage model in src/models/slack_message.py with all required fields and validation rules
- [ ] T019 [P] [US1] Create NotionPage model in src/models/notion_page.py with page creation and metadata tracking
- [ ] T020 [P] [US1] Create ProcessingQueue model in src/models/processing_queue.py for task management and retry logic
- [ ] T021 [US1] Implement Slack command handler service in src/services/slack/command_handler.py for /create-notion processing
- [ ] T022 [US1] Implement Notion page creation service in src/services/notion/page_creator.py with content formatting
- [ ] T023 [US1] Implement Slack markup to Notion formatting converter in src/services/processing/content_formatter.py
- [ ] T024 [US1] Create slash command endpoint in src/services/slack/slash_commands.py with webhook verification
- [ ] T025 [US1] Integrate command processing with queue system and rate limiting
- [ ] T026 [US1] Add command response handling with Slack confirmation messages and error feedback
- [ ] T027 [US1] Implement database persistence for SlackMessage and NotionPage entities

**Checkpoint**: At this point, `/create-notion` command should create Notion pages and provide Slack confirmations

---

## Phase 4: User Story 2 - Keyword-Based Message Aggregation (Priority: P2)

**Goal**: Monitor Slack channels for keywords and generate scheduled aggregation reports in Notion

**Independent Test**: Configure keyword monitoring for test channel, post messages with target keywords over time, verify scheduled reports are generated in Notion

### Implementation for User Story 2

- [ ] T028 [P] [US2] Create KeywordRule model in src/models/keyword_rule.py with monitoring configuration and validation
- [ ] T029 [P] [US2] Create SummaryReport model in src/models/summary_report.py for aggregated content tracking
- [ ] T030 [US2] Implement Slack event listener service in src/services/slack/event_listener.py for real-time message monitoring
- [ ] T031 [US2] Implement keyword matching engine in src/services/processing/keyword_matcher.py with regex, exact, and contains modes
- [ ] T032 [US2] Create message aggregation service in src/services/processing/message_aggregator.py for grouping and summarizing
- [ ] T033 [US2] Implement scheduled job system with APScheduler in src/scheduling/scheduler.py
- [ ] T034 [US2] Create keyword rule management API endpoints in src/services/api/keyword_rules.py
- [ ] T035 [US2] Implement aggregation report generation in src/services/notion/report_generator.py
- [ ] T036 [US2] Add keyword rule CRUD operations with validation and persistence
- [ ] T037 [US2] Integrate aggregation reports with Notion page creation workflow from User Story 1

**Checkpoint**: At this point, keyword monitoring and scheduled aggregation reports should be fully functional

---

## Phase 5: User Story 3 - Thread and History Summarization (Priority: P3)

**Goal**: Provide on-demand summarization of Slack threads and channel history via commands

**Independent Test**: Create test thread with multiple participants, use `/summarize-thread`, verify coherent summary is generated and saved to Notion

### Implementation for User Story 3

- [ ] T038 [P] [US3] Implement thread retrieval service in src/services/slack/thread_reader.py for fetching conversation history
- [ ] T039 [P] [US3] Implement channel history service in src/services/slack/history_reader.py with timeframe parsing
- [ ] T040 [P] [US3] Create text summarization engine in src/services/processing/summarizer.py for content analysis
- [ ] T041 [US3] Add `/summarize-thread` command handler in src/services/slack/command_handler.py
- [ ] T042 [US3] Add `/summarize-channel` command handler with timeframe support in src/services/slack/command_handler.py
- [ ] T043 [US3] Implement participant identification and key topic extraction in src/services/processing/content_analyzer.py
- [ ] T044 [US3] Create summary formatting service in src/services/processing/summary_formatter.py for structured output
- [ ] T045 [US3] Integrate thread and channel summarization with existing Notion page creation workflow
- [ ] T046 [US3] Add action item detection and decision tracking in summary generation
- [ ] T047 [US3] Implement summary metadata storage and retrieval for report tracking

**Checkpoint**: At this point, both thread and channel summarization commands should generate comprehensive summaries

---

## Phase 6: User Story 4 - Duplicate Message Organization (Priority: P4)

**Goal**: Detect and consolidate duplicate messages into unified Notion pages with source references

**Independent Test**: Post similar messages in different channels, verify application identifies duplicates and creates unified Notion pages with proper source references

### Implementation for User Story 4

- [ ] T048 [P] [US4] Create DuplicateGroup model in src/models/duplicate_group.py for tracking similar messages
- [ ] T049 [P] [US4] Implement content similarity detection in src/services/processing/duplicate_detector.py using difflib and configurable thresholds
- [ ] T050 [P] [US4] Create message consolidation service in src/services/processing/message_consolidator.py
- [ ] T051 [US4] Implement duplicate detection job in src/scheduling/duplicate_jobs.py for periodic scanning
- [ ] T052 [US4] Create duplicate management API endpoints in src/services/api/duplicates.py for manual override
- [ ] T053 [US4] Implement consolidated page generation in src/services/notion/consolidation_service.py
- [ ] T054 [US4] Add source message reference tracking and link generation
- [ ] T055 [US4] Integrate duplicate detection with existing message processing pipeline
- [ ] T056 [US4] Implement user notification system for duplicate consolidation events
- [ ] T057 [US4] Add duplicate group status management (active, merged, split, archived)

**Checkpoint**: All user stories should now be independently functional with comprehensive duplicate management

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories and production readiness

- [ ] T058 [P] Implement comprehensive error handling and user-friendly error messages across all services
- [ ] T059 [P] Add audit logging for all API interactions and page creations in src/services/audit_logger.py
- [ ] T060 [P] Create CLI commands for database initialization and migration in src/cli/database.py
- [ ] T061 [P] Implement circuit breaker pattern for external API resilience in src/services/circuit_breaker.py
- [ ] T062 [P] Add configuration validation and startup health checks in src/config/validator.py
- [ ] T063 [P] Create monitoring and metrics collection endpoints in src/services/monitoring.py
- [ ] T064 [P] Implement graceful shutdown handling for background jobs and connections
- [ ] T065 [P] Add request/response logging and performance monitoring
- [ ] T066 [P] Create API documentation generation from OpenAPI specification
- [ ] T067 Run quickstart.md validation and integration testing

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-6)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3 → P4)
- **Polish (Phase 7)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - Integrates with US1 for Notion page creation but independently testable
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - Uses US1 page creation workflow but independently testable
- **User Story 4 (P4)**: Can start after Foundational (Phase 2) - Uses US1 page creation workflow but independently testable

### Within Each User Story

- Models before services (data structures must exist before business logic)
- Core services before integration services (base functionality before orchestration)
- API endpoints after service implementation
- Story integration after core implementation
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tasks marked [P] can run in parallel (within Phase 2)
- Once Foundational phase completes, all user stories can start in parallel (if team capacity allows)
- Models within a story marked [P] can run in parallel
- Services within a story marked [P] can run in parallel
- Different user stories can be worked on in parallel by different team members

---

## Parallel Example: User Story 1

```bash
# Launch all models for User Story 1 together:
Task: "Create SlackMessage model in src/models/slack_message.py"
Task: "Create NotionPage model in src/models/notion_page.py"
Task: "Create ProcessingQueue model in src/models/processing_queue.py"

# Launch after models complete:
Task: "Implement Slack command handler service in src/services/slack/command_handler.py"
Task: "Implement Notion page creation service in src/services/notion/page_creator.py"
Task: "Implement content formatter in src/services/processing/content_formatter.py"
```

---

## Parallel Example: User Story 2

```bash
# Launch all models for User Story 2 together:
Task: "Create KeywordRule model in src/models/keyword_rule.py"
Task: "Create SummaryReport model in src/models/summary_report.py"

# Launch after models complete:
Task: "Implement Slack event listener service in src/services/slack/event_listener.py"
Task: "Implement keyword matching engine in src/services/processing/keyword_matcher.py"
Task: "Create message aggregation service in src/services/processing/message_aggregator.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (Slack Command to Notion Page Creation)
4. **STOP and VALIDATE**: Test `/create-notion` command independently with real Slack workspace and Notion database
5. Deploy/demo MVP - core value proposition of bridging Slack conversations to persistent Notion documentation

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (MVP! Core slash command functionality)
3. Add User Story 2 → Test independently → Deploy/Demo (Automated keyword monitoring and aggregation)
4. Add User Story 3 → Test independently → Deploy/Demo (On-demand summarization capabilities)
5. Add User Story 4 → Test independently → Deploy/Demo (Duplicate detection and consolidation)
6. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (MVP priority)
   - Developer B: User Story 2 (Keyword aggregation)
   - Developer C: User Story 3 (Summarization)
   - Developer D: User Story 4 (Duplicate detection)
3. Stories complete and integrate independently

---

## Task Summary

- **Total Tasks**: 67
- **Setup Phase**: 6 tasks
- **Foundational Phase**: 11 tasks
- **User Story 1 (P1)**: 10 tasks
- **User Story 2 (P2)**: 10 tasks
- **User Story 3 (P3)**: 10 tasks
- **User Story 4 (P4)**: 10 tasks
- **Polish Phase**: 10 tasks

**Parallel Opportunities**: 41 tasks marked [P] can run in parallel within their phase constraints

**Independent Test Criteria**: Each user story has clear acceptance criteria and can be tested independently with real Slack workspaces and Notion databases

**Suggested MVP Scope**: User Story 1 only (Tasks T001-T027) provides core value proposition of Slack-to-Notion page creation

**Format Validation**: All tasks follow required checklist format with checkbox, sequential ID, optional [P] and [Story] labels, and specific file paths

---

## Notes

- [P] tasks = different files, no dependencies within phase
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Constitution compliance maintained through TDD approach, proper error handling, and modular architecture
- Rate limiting and API safety built into foundational phase to prevent violations
- All external API interactions include retry logic and circuit breaker patterns
- Configuration externalized and validated per constitutional requirements