<!--
Sync Impact Report:
Version change: N/A → 1.0.0
Added principles:
- I. Test-First Development (NON-NEGOTIABLE)
- II. Code Quality Standards  
- III. Environment Safety
- IV. API Integration Safety
- V. Modular Architecture
Added sections:
- Security & Safety Requirements
- Development Workflow
Templates requiring updates:
✅ Updated plan-template.md (Constitution Check section aligns)
✅ Updated spec-template.md (testing requirements align)
✅ Updated tasks-template.md (TDD task ordering aligns)
Follow-up TODOs: None - all placeholders filled
-->

# Meowth Constitution

## Core Principles

### I. Test-First Development (NON-NEGOTIABLE)
TDD mandatory for all code: Tests MUST be written first, reviewed and approved, MUST fail initially, then implementation follows. Red-Green-Refactor cycle strictly enforced. No code merges without corresponding tests that validate the intended behavior.

**Rationale**: Prevents regressions, ensures reliable integrations with external APIs (Slack/Notion), and maintains system stability as complexity grows.

### II. Code Quality Standards
All code MUST follow established quality gates: automated linting (flake8/black for Python), type hints mandatory, maximum function complexity limits enforced, documentation required for all public interfaces, and consistent naming conventions across the codebase.

**Rationale**: External API integrations require reliable, maintainable code that can handle evolving third-party dependencies and complex data transformations.

### III. Environment Safety
Environment-specific configurations MUST be externalized and validated. No hardcoded credentials, API keys, or environment-specific values in source code. All external dependencies MUST be pinned with explicit version ranges. Development, staging, and production environments MUST be isolated.

**Rationale**: Multi-API integration (Slack + Notion) requires secure credential management and consistent behavior across deployment environments.

### IV. API Integration Safety
All external API calls MUST implement proper error handling, rate limiting respect, timeout controls, and retry logic with exponential backoff. Circuit breaker patterns required for critical paths. All API responses MUST be validated before processing.

**Rationale**: Slack and Notion APIs have different rate limits, error patterns, and availability characteristics that require defensive programming practices.

### V. Modular Architecture
Each feature MUST be implemented as independently testable modules with clear interfaces. API clients, data processing, and scheduling logic MUST be separated into distinct layers. Shared schemas and data models MUST be versioned and backward-compatible.

**Rationale**: Enables independent testing of Slack monitoring, Notion page creation, and message aggregation without requiring full system integration.

## Security & Safety Requirements

**Credential Management**: All API tokens and sensitive configuration MUST use environment variables or secure secret management. No credentials in logs, error messages, or debug output.

**Data Privacy**: Slack message content MUST be handled according to data retention policies. Personal information MUST be scrubbed from logs and error reports.

**Rate Limiting**: MUST respect both Slack (50+ requests per minute) and Notion API limits. Implement queuing and backoff strategies to prevent service disruption.

**Error Boundaries**: System MUST continue operating when one API is unavailable. Graceful degradation required for partial failures.

## Development Workflow

**Code Review Gates**: All changes MUST pass automated tests, linting, type checking, and manual review before merge. Constitution compliance verified in PR template.

**Testing Requirements**: Unit tests for all business logic, integration tests for API interactions, contract tests for data transformations. Minimum 90% code coverage maintained.

**Deployment Safety**: Staged deployments required. Health checks MUST verify API connectivity before traffic routing. Rollback procedures documented and tested.

**Documentation**: All modules MUST include docstrings, API integration patterns MUST be documented with examples, deployment procedures MUST be automated and documented.

## Governance

This constitution supersedes all other development practices and MUST be verified during all code reviews. Any complexity that violates these principles MUST be explicitly justified with documented rationale and simpler alternatives considered. 

Version changes require full team review and migration planning. All amendments MUST maintain backward compatibility with existing templates and workflows.

**Version**: 1.0.0 | **Ratified**: 2025-11-06 | **Last Amended**: 2025-11-06
