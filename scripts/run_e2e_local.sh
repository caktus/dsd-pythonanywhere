#!/bin/bash
set -e

# Run the PythonAnywhere e2e deployment test locally, mirroring
# .github/workflows/e2e_pythonanywhere.yaml.
#
# Usage:
#   cd dsd-pythonanywhere && git checkout <pr-branch>
#   cp .env.e2e.example .env.e2e   # first time only; fill in real values
#   ./scripts/run_e2e_local.sh
#
# Required env vars (loaded from .env.e2e if present, in the plugin root):
#   API_USER        PythonAnywhere username
#   API_TOKEN       PythonAnywhere API token
#   PA_PASSWORD     PythonAnywhere login password (for the headless console opener)
#   DEMO_REPO_URL   Push URL for the scratch repo PA will clone, with embedded
#                   credentials, e.g. https://x-access-token:<token>@github.com/owner/repo.git
#   DEMO_REPO_NAME  Repo name only, e.g. dsd-pythonanywhere-testproj
#
# Assumes django-simple-deploy is checked out as a sibling directory; override
# with DSD_ROOT=/path/to/django-simple-deploy.

PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DSD_ROOT="${DSD_ROOT:-$PLUGIN_ROOT/../django-simple-deploy}"

if [ -f "$PLUGIN_ROOT/.env.e2e" ]; then
	echo "Loading env vars from .env.e2e..."
	set -a
	source "$PLUGIN_ROOT/.env.e2e"
	set +a
fi

for var in API_USER API_TOKEN PA_PASSWORD DEMO_REPO_URL DEMO_REPO_NAME; do
	if [ -z "${!var:-}" ]; then
		echo "Missing required env var: $var (set it, or add it to .env.e2e)" >&2
		exit 1
	fi
done

if [ ! -d "$DSD_ROOT" ]; then
	echo "django-simple-deploy not found at $DSD_ROOT (set DSD_ROOT to override)" >&2
	exit 1
fi

export DSD_PYTHONANYWHERE_CONSOLE_OPENER="e2e_tests.pa_admin:open_console"
export PYTHONPATH="$PLUGIN_ROOT/tests"

cd "$DSD_ROOT"

echo "Installing dependencies..."
uv venv
uv pip install -e .
uv pip install -e "$PLUGIN_ROOT[dev]"
uv run playwright install chromium --with-deps

echo "Pre-test cleanup (webapp + filesystem)..."
uv run python -m e2e_tests.pa_admin

echo "Running e2e test..."
uv run pytest tests/e2e_tests --plugin dsd_pythonanywhere --automate-all --skip-confirmations -s

echo "Teardown..."
uv run python -m e2e_tests.pa_admin
