import os
import time

import pytest

from tests.e2e_tests.utils import it_helper_functions as it_utils

from . import utils as platform_utils

# --- Test functions ---


# For normal test runs, skip this test.
# When working on setup steps, skip other tests and run this one.
#   This will force the tmp_project fixture to run, without doing a full deployment.
@pytest.mark.skip
def test_dummy(tmp_project, request):
    """Helpful to have an empty test to run when testing setup steps."""
    pass


def _configure_demo_repo_remote(tmp_project):
    """Point tmp_project at the real GitHub repo PythonAnywhere will clone from.

    The plugin pushes to `origin` and has PA `git clone` that same URL, so a
    real, internet-reachable remote is required -- tmp_project only has a
    local git history (see manage_sample_project.py), and it's brand new on
    every run, so it's force-pushed onto the remote's `main` branch first.
    This makes the plugin's later plain (non-force) `git push origin HEAD` a
    fast-forward, without needing branch-deletion permission on the remote.
    """
    demo_repo_url = os.environ["DEMO_REPO_URL"]
    it_utils.make_sp_call(f"git -C {tmp_project} remote add origin {demo_repo_url}")
    result = it_utils.make_sp_call(
        f"git -C {tmp_project} push --force origin HEAD:main", capture_output=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to reset demo repo's main branch: {result.stderr.decode()}")


# Skip this test and enable test_dummy() to speed up testing of setup steps.
# @pytest.mark.skip
def test_deployment(tmp_project, cli_options, request):
    """Test the full, live deployment process to PythonAnywhere."""

    # Cache the platform name for teardown work.
    request.config.cache.set("platform", "dsd_pythonanywhere")

    print("\nTesting deployment to PythonAnywhere using the following options:")
    print(cli_options.__dict__)

    python_cmd = it_utils.get_python_exe(tmp_project)

    # PythonAnywhere's webapp is tied to the account, so only automate_all is
    # supported here; a non-automated flow doesn't have a project to create first.
    if not cli_options.automate_all:
        raise NotImplementedError(
            "dsd-pythonanywhere e2e tests only support the --automate-all workflow."
        )

    _configure_demo_repo_remote(tmp_project)

    # Run simple_deploy against the test project.
    it_utils.run_simple_deploy(python_cmd, automate_all=cli_options.automate_all)

    # If testing Pipenv, lock after adding new packages.
    if cli_options.pkg_manager == "pipenv":
        it_utils.make_sp_call(f"{python_cmd} -m pipenv lock")

    # Get the deployed project's URL and app name, and cache app_name for teardown.
    project_url, app_name = platform_utils.get_project_url_name()
    request.config.cache.set("app_name", app_name)

    # Remote functionality test often fails if run too quickly after deployment.
    print("\nPausing 10s to let deployment finish...")
    time.sleep(10)

    # Test functionality of both deployed app, and local project.
    #   We want to make sure the deployment works, but also make sure we haven't
    #   affected functionality of the local project using the development server.
    remote_functionality_passed = it_utils.check_deployed_app_functionality(python_cmd, project_url)
    local_functionality_passed = it_utils.check_local_app_functionality(python_cmd)
    log_check_passed = platform_utils.check_log(tmp_project)

    it_utils.summarize_results(
        remote_functionality_passed,
        local_functionality_passed,
        cli_options,
        tmp_project,
    )

    # Make final assertions, so pytest results are meaningful.
    assert remote_functionality_passed
    assert local_functionality_passed
    assert log_check_passed
