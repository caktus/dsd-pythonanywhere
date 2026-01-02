"""Manages all PythonAnywhere-specific aspects of the deployment process."""

import os
import webbrowser
from pathlib import Path

from django_simple_deploy.management.commands.utils import plugin_utils
from django_simple_deploy.management.commands.utils.command_errors import DSDCommandError
from django_simple_deploy.management.commands.utils.plugin_utils import dsd_config

from dsd_pythonanywhere.client import PythonAnywhereClient

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
        self.api_user = os.getenv("API_USER", "")
        self.client = PythonAnywhereClient(username=self.api_user)

    # --- Public methods ---

    def deploy(self, *args, **options):
        """Coordinate the overall configuration and deployment."""
        plugin_utils.write_output("\nConfiguring project for deployment to PythonAnywhere...")

        self._validate_platform()

        if dsd_config.automate_all:
            self._prep_automate_all()

        # Configure project for deployment to PythonAnywhere
        self._add_requirements()
        self._modify_settings()
        self._modify_wsgi()
        self._modify_gitignore()

        self._conclude_automate_all()
        self._show_success_message()

    # --- Helper methods for deploy() ---

    def _get_deployed_project_name(self) -> str:
        return self.api_user

    def _validate_platform(self) -> None:
        """Make sure the local environment and project supports deployment to PythonAnywhere.

        Raises:
            DSDCommandError: If we find any reason deployment won't work.
        """
        # Only validate API credentials when actually deploying
        if not dsd_config.automate_all:
            return

        # Check for required environment variables
        if not os.getenv("API_USER"):
            raise DSDCommandError(
                "API_USER environment variable is not set. "
                "Please set it to your PythonAnywhere username."
            )

        if not os.getenv("API_TOKEN"):
            raise DSDCommandError(
                "API_TOKEN environment variable is not set. "
                "Please set it to your PythonAnywhere API token."
            )

        # Test API connection
        try:
            self.client.request(method="GET", url=self.client._base_url("cpu"))
        except Exception as e:
            raise DSDCommandError(
                f"Failed to connect to PythonAnywhere API: {e}. "
                "Please verify your API_USER and API_TOKEN are correct."
            )

    def _get_origin_url(self) -> str:
        """Get the git remote origin URL."""
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

    def _get_repo_name(self) -> str:
        """Get the repository name from the git remote URL.

        Falls back to the project root directory name if no remote is configured.
        """
        try:
            origin_url = self._get_origin_url()
            return Path(origin_url).stem
        except Exception:
            # No remote configured, use project directory name
            return dsd_config.project_root.name

    def _prep_automate_all(self):
        """Configure paths and repo info for automate_all deployment.

        Caveats: Git commands will fail in test environments without a remote
        configured.
        """
        self.repo_origin_url = self._get_origin_url()
        self.repo_name = self._get_repo_name()
        self.pa_home = Path(f"/home/{self.client.username}")
        self.pa_project_root_path = self.pa_home / self.repo_name

    def _clone_and_run_setup_script(self):
        # Run the setup script to clone repo and install dependencies
        cmd = [f"curl -fsSL {REMOTE_SETUP_SCRIPT_URL} | bash -s --"]
        origin_url = self._get_origin_url()
        django_project_name = dsd_config.local_project_name
        cmd.append(f"{origin_url} {self.repo_name} {django_project_name}")
        cmd = " ".join(cmd)
        plugin_utils.write_output(f"  Cloning and running setup script: {cmd}")
        self.client.run_command(cmd)
        plugin_utils.write_output("Done cloning and running setup script.")

    def _copy_wsgi_file(self):
        """Copy wsgi.py to PythonAnywhere's wsgi location.

        This must be done after webapp creation, as creating a webapp
        overwrites the wsgi file.
        """
        plugin_utils.write_output("  Copying wsgi.py to PythonAnywhere...")

        django_project_name = dsd_config.local_project_name
        domain = f"{self.client.username}.pythonanywhere.com"
        wsgi_dest = f"/var/www/{domain.replace('.', '_')}_wsgi.py"
        wsgi_src = f"{self.repo_name}/{django_project_name}/wsgi.py"

        cmd = f"cp {wsgi_src} {wsgi_dest}"
        self.client.run_command(cmd)
        plugin_utils.write_output(f"  Copied {wsgi_src} to {wsgi_dest}")

    def _create_webapp(self):
        """Create the webapp on PythonAnywhere."""
        plugin_utils.write_output("  Creating webapp on PythonAnywhere...")
        self.client.create_webapp_if_not_exists(
            python_version="3.13",
            virtualenv_path=self.pa_home / "venv",
            project_path=self.pa_project_root_path,
        )
        plugin_utils.write_output("Webapp created and configured.")

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
        - Create webapp.
        - Copy wsgi file.
        - Configure static files.
        - Reload webapp.
        """
        # Making this check here lets deploy() be cleaner.
        if not dsd_config.automate_all:
            return

        plugin_utils.commit_changes()
        # Push to remote (GitHub, etc).
        plugin_utils.write_output("Pushing changes to remote repository...")
        plugin_utils.run_quick_command("git push origin HEAD", check=True)

        # Deploy project.
        plugin_utils.write_output("Deploying to PythonAnywhere...")
        self._clone_and_run_setup_script()
        self._create_webapp()
        self._copy_wsgi_file()
        self.client.reload_webapp()
        self.deployed_url = f"https://{self._get_deployed_project_name()}.pythonanywhere.com"

    def _show_success_message(self):
        """After a successful run, show a message about what to do next.

        Describe ongoing approach of commit, push, migrate.
        """
        if dsd_config.automate_all:
            msg = platform_msgs.success_msg_automate_all(self.deployed_url)
            webbrowser.open(self.deployed_url)
        else:
            msg = platform_msgs.success_msg(log_output=dsd_config.log_output)
        plugin_utils.write_output(msg)
