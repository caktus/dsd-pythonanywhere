"""Manages all PythonAnywhere-specific aspects of the deployment process.

Notes:
-

Add a new file to the user's project, without using a template:

    def _add_dockerignore(self):
        # Add a dockerignore file, based on user's local project environmnet.
        path = dsd_config.project_root / ".dockerignore"
        dockerignore_str = self._build_dockerignore()
        plugin_utils.add_file(path, dockerignore_str)

Add a new file to the user's project, using a template:

    def _add_dockerfile(self):
        # Add a minimal dockerfile.
        template_path = self.templates_path / "dockerfile_example"
        context = {
            "django_project_name": dsd_config.local_project_name,
        }
        contents = plugin_utils.get_template_string(template_path, context)

        # Write file to project.
        path = dsd_config.project_root / "Dockerfile"
        plugin_utils.add_file(path, contents)

Modify user's settings file:

    def _modify_settings(self):
        # Add platformsh-specific settings.
        template_path = self.templates_path / "settings.py"
        context = {
            "deployed_project_name": self._get_deployed_project_name(),
        }
        plugin_utils.modify_settings_file(template_path, context)

Add a set of requirements:

    def _add_requirements(self):
        # Add requirements for deploying to Fly.io.
        requirements = ["gunicorn", "psycopg2-binary", "dj-database-url", "whitenoise"]
        plugin_utils.add_packages(requirements)
"""

import os
from pathlib import Path

from django_simple_deploy.management.commands.utils import plugin_utils
from django_simple_deploy.management.commands.utils.plugin_utils import dsd_config

from dsd_pythonanywhere.client import APIClient

from . import deploy_messages as platform_msgs

REMOTE_SETUP_SCRIPT_URL = os.getenv(
    "REMOTE_SETUP_SCRIPT_URL",
    "https://raw.githubusercontent.com/caktus/dsd-pythonanywhere/refs/heads/main/scripts/setup.sh",
)
PLUGIN_REQUIREMENTS = (
    "dsd-pythonanywhere @ git+https://github.com/caktus/dsd-pythonanywhere@main",
    "python-dotenv",
    "dj-database-url",
)


class PlatformDeployer:
    """Perform the initial deployment to PythonAnywhere

    If --automate-all is used, carry out an actual deployment.
    If not, do all configuration work so the user only has to commit changes, and ...
    """

    def __init__(self):
        self.templates_path = Path(__file__).parent / "templates"

    # --- Public methods ---

    def deploy(self, *args, **options):
        """Coordinate the overall configuration and deployment."""
        plugin_utils.write_output("\nConfiguring project for deployment to PythonAnywhere...")

        self._validate_platform()
        self._prep_automate_all()

        # Configure project for deployment to PythonAnywhere
        self._add_requirements()
        self._modify_settings()
        self._modify_wsgi()
        self._modify_gitignore()

        self._conclude_automate_all()
        self._show_success_message()

    # --- Helper methods for deploy() ---

    def _validate_platform(self):
        """Make sure the local environment and project supports deployment to PythonAnywhere.

        Returns:
            None
        Raises:
            DSDCommandError: If we find any reason deployment won't work.
        """
        pass

    def _get_origin_url(self) -> str:
        """"""
        origin_url = (
            plugin_utils.run_quick_command("git config --get remote.origin.url", check=True)
            .stdout.decode()
            .strip()
        )

        # Convert SSH URL to HTTPS URL
        # git@github.com:owner/repo.git -> https://github.com/owner/repo.git
        if origin_url.startswith("git@"):
            # Remove 'git@' and replace ':' after hostname with '/'
            https_url = origin_url.replace("git@", "https://").replace("github.com:", "github.com/")
        else:
            https_url = origin_url

        return https_url

    def _get_deployed_project_name(self):
        return os.getenv("API_USER")

    def _get_repo_name(self) -> str:
        """Get the repository name from the git remote URL."""
        origin_url = self._get_origin_url()
        return Path(origin_url).stem

    def _prep_automate_all(self):
        """Take any further actions needed if using automate_all."""
        pass

    def _clone_and_run_setup_script(self):
        client = APIClient(username=os.getenv("API_USER"))
        # Proof of concept to run script remotely on Python Anywhere
        cmd = [f"curl -fsSL {REMOTE_SETUP_SCRIPT_URL} | bash -s --"]
        origin_url = self._get_origin_url()
        repo_name = self._get_repo_name()
        cmd.append(f"{origin_url} {repo_name}")
        cmd = " ".join(cmd)
        plugin_utils.write_output(f"  Cloning and running setup script: {cmd}")
        client.run_command(cmd)
        plugin_utils.write_output("Done cloning and running setup script.")

    def _add_requirements(self):
        """Add requirements for deploying to PythonAnywhere."""
        plugin_utils.write_output("  Adding deploy requirements...")
        plugin_utils.add_packages(PLUGIN_REQUIREMENTS)

    def _modify_settings(self):
        """Add platformsh-specific settings."""
        plugin_utils.write_output("  Modifying settings.py for PythonAnywhere...")
        template_path = self.templates_path / "settings.py"
        context = {"deployed_project_name": self._get_deployed_project_name()}
        plugin_utils.modify_settings_file(template_path, context)

    def _modify_wsgi(self):
        """Modify wsgi.py for PythonAnywhere deployment."""
        plugin_utils.write_output("  Modifying wsgi.py for PythonAnywhere...")
        template_path = self.templates_path / "wsgi.py"
        context = {
            "django_project_name": dsd_config.local_project_name,
            "repo_name": self._get_repo_name(),
        }
        contents = plugin_utils.get_template_string(template_path, context)
        path = dsd_config.project_root / dsd_config.local_project_name / "wsgi.py"
        plugin_utils.add_file(path, contents)

    def _modify_gitignore(self) -> None:
        """Ensure .gitignore ignores deployment files."""
        patterns = [".env"]
        gitignore_path = dsd_config.git_path / ".gitignore"
        if not gitignore_path.exists():
            # Make the .gitignore file with patterns.
            gitignore_path.write_text("\n".join(patterns), encoding="utf-8")
            plugin_utils.write_output("No .gitignore file found; created .gitignore.")
            plugin_utils.write_output("Added .env to .gitignore.")
        else:
            # Append patterns to .gitignore if not already there.
            contents = gitignore_path.read_text()
            patterns_to_add = "".join([pattern for pattern in patterns if pattern not in contents])
            contents += f"\n{patterns_to_add}"
            gitignore_path.write_text(contents)
            plugin_utils.write_output(f"Added {patterns_to_add} to .gitignore")

    def _conclude_automate_all(self):
        """Finish automating the push to PythonAnywhere.

        - Commit all changes.
        - Push to remote repo.
        - Run setup script on PythonAnywhere.
        """
        # Making this check here lets deploy() be cleaner.
        if not dsd_config.automate_all:
            return

        plugin_utils.commit_changes()
        # Push to remote (GitHub, etc).
        plugin_utils.write_output("  Pushing changes to remote repository...")
        plugin_utils.run_quick_command("git push origin HEAD", check=True)

        # Push project.
        plugin_utils.write_output("  Deploying to PythonAnywhere...")

        # Should set self.deployed_url, which will be reported in the success message.
        self._clone_and_run_setup_script()
        self.deployed_url = f"https://{self._get_deployed_project_name()}.pythonanywhere.com"

    def _show_success_message(self):
        """After a successful run, show a message about what to do next.

        Describe ongoing approach of commit, push, migrate.
        """
        if dsd_config.automate_all:
            msg = platform_msgs.success_msg_automate_all(self.deployed_url)
        else:
            msg = platform_msgs.success_msg(log_output=dsd_config.log_output)
        plugin_utils.write_output(msg)
