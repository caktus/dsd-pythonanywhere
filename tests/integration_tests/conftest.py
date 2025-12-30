"""Conftest for dsd-pythonanywhere integration tests.

Re-export fixtures from django-simple-deploy's integration tests.
"""

from tests.integration_tests.conftest import dsd_version as dsd_version  # noqa: F401
from tests.integration_tests.conftest import pkg_manager as pkg_manager  # noqa: F401
from tests.integration_tests.conftest import (
    reset_test_project as reset_test_project,
)  # noqa: F401
from tests.integration_tests.conftest import run_dsd as run_dsd  # noqa: F401
from tests.integration_tests.conftest import tmp_project as tmp_project  # noqa: F401
