# AGENTS.md

This file provides guidance when working with code in this repository.

## Project Overview

dsd-pythonahwyhere is a plugin for deploying Django projects to PythonAnywhere, using django-simple-deploy.

## Development Commands

### Environment Setup

- `uv` is used for Python dependency management.
- Install Python dependencies: `uv sync`
- Add Python dependencies: `uv add <library>` or `uv add --group dev <library>` for dev-only
- You can run generic Python commands using `uv run <command>`

### Testing

- Run tests with pytest: `uv run pytest`
- Tests are located in the `tests/` directory and follow standard pytest and pytest-mock conventions.
- New features and bug fixes should always include a concise test (not exhaustive).

### Code Quality

- Run pre-commit hooks: `uv run pre-commit run --all-files`. Always run this after making changes.
- Format Python code with Ruff: `uv run ruff format .`
- Lint and auto-fix Python code: `uv run ruff check --fix .`
