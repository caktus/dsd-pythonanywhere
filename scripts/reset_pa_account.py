"""Wipe PythonAnywhere account state so each e2e run starts clean.

setup.sh skips re-cloning/re-creating the venv if they already exist, so a
dirty account from a prior run won't self-clean; run this explicitly before
(and after, via `if: always()`) each e2e workflow run.

Requires API_USER, API_TOKEN, and DEMO_REPO_NAME environment variables.
"""

import os

from dsd_pythonanywhere.client import PythonAnywhereClient


def main() -> None:
    repo_name = os.environ["DEMO_REPO_NAME"]
    client = PythonAnywhereClient(username=os.environ["API_USER"])

    if client.webapp_exists():
        print("Deleting existing webapp...")
        client.webapp.delete()

    print(f"Removing ~/{repo_name} and ~/venv...")
    client.run_command(f"rm -rf ~/{repo_name} ~/venv")


if __name__ == "__main__":
    main()
