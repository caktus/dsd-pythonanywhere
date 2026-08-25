"""Helper functions specific to PythonAnywhere e2e tests."""

import os

from dsd_pythonanywhere.client import PythonAnywhereClient


def get_client() -> PythonAnywhereClient:
    """Return a client for the account under test."""
    return PythonAnywhereClient(username=os.environ["API_USER"])


def get_project_url_name():
    """Get project URL and app name of a deployed project.

    PythonAnywhere's webapp is tied to the account, so both are deterministic
    once deployment is complete; this is used when testing the automate_all
    workflow.
    """
    app_name = os.environ["API_USER"]
    project_url = f"https://{app_name}.pythonanywhere.com"

    print(f"  Found app name: {app_name}")
    print(f"  Project URL: {project_url}")

    return project_url, app_name


def check_log(tmp_proj_dir):
    """Check the log that was generated during a full deployment.

    Checks that log file exists, and that DATABASE_URL is not logged.
    """
    path = tmp_proj_dir / "simple_deploy_logs"
    if not path.exists():
        return False

    log_files = list(path.glob("simple_deploy_*.log"))
    if not log_files:
        return False

    log_str = log_files[0].read_text()
    if "DATABASE_URL" in log_str:
        return False

    return True


def destroy_project(request):
    """Destroy the deployed project, and all remote resources."""
    print("\nCleaning up:")

    app_name = request.config.cache.get("app_name", None)
    if not app_name:
        print("  No app name found; can't destroy any remote resources.")
        return None

    print("  Destroying PythonAnywhere webapp...")
    client = get_client()
    client.webapp.delete()
