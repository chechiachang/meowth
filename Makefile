# Meowth Development Makefile

.PHONY: help test test-unit test-integration test-contract test-all clean lint format type-check install dev-install

# Default target
help:
	@echo "Available targets:"
	@echo "  test           - Run all tests"
	@echo "  test-unit      - Run unit tests only"
	@echo "  test-integration - Run integration tests only"
	@echo "  test-contract  - Run contract tests only"
	@echo "  test-coverage  - Run tests with coverage report"
	@echo "  lint           - Run linting (ruff)"
	@echo "  format         - Format code (ruff format)"
	@echo "  type-check     - Run type checking (mypy)"
	@echo "  quality        - Run all quality checks (lint + type-check)"
	@echo "  install        - Install dependencies"
	@echo "  dev-install    - Install with dev dependencies"
	@echo "  clean          - Clean up cache files"
	@echo "  run            - Run the application"

# Test targets
test:
	PYTHONWARNINGS=ignore uv run pytest tests/ -v

test-unit:
	uv run pytest tests/unit/ -v

test-integration:
	uv run pytest tests/integration/ -v

test-contract:
	uv run pytest tests/contract/ -v

test-all: test-unit test-integration test-contract

test-coverage:
	uv run pytest tests/ -v --cov=src/meowth --cov-report=html --cov-report=term

# Quality targets
format:
	uv run ruff format src/meowth tests/

lint:
	uv run ruff check --fix src/meowth tests/

type-check:
	uv run mypy src/meowth

quality: format lint type-check

# Installation targets
install:
	uv sync

dev-install:
	uv sync --dev

# Application targets
run:
	uv run meowth

run-debug:
	uv run meowth --log-level DEBUG

# Utility targets
clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache __pycache__ .coverage htmlcov/
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} +

# Development workflow
dev: dev-install quality test-all
	@echo "✅ Development environment ready!"

# CI/CD workflow
ci: install quality test-coverage
	@echo "✅ CI checks passed!"

# Legacy targets for backward compatibility
type: type-check
all: quality test
