# AGENTS.md

This file provides guidance when working with code in this repository.

## Project Overview

dsd-pythonanywhere is a plugin for deploying Django projects to PythonAnywhere, using django-simple-deploy.

## Development Commands

### Environment Setup

- `uv` is used for Python dependency management.
- Install Python dependencies: `uv sync`
- Add Python dependencies: `uv add <library>` or `uv add --group dev <library>` for dev-only
- You can run generic Python commands using `uv run <command>`

### Testing

- Run tests with pytest: `uv run pytest`
- Tests are located in the `tests/` directory and follow standard pytest and pytest-mock conventions.
- Integration tests (in `dsd-pythonanywhere/tests/integration_tests`) must be run from the `django-simple-deploy` project root. See `.github/workflows/integration_tests.yaml` for test setup details.
- Use `-k` to filter tests by name pattern, e.g., `uv run pytest -k "test_setup_script"` to run only setup script tests.
- Add or update tests for the code you change, even if nobody asked.
- New features and bug fixes should always include a concise test (not exhaustive).
- Always run full test suite and ruff pre-commit hooks as the last tasks in your todo list

### Code Quality

- Run ruff pre-commit hooks: `uv run pre-commit run --all-files`.
