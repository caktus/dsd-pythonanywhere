<!-- omit in toc -->
# dsd-pythonanywhere

<div align="center">
  <a target="_blank" href="https://github.com/caktus/dsd-pythonanywhere/blob/main/LICENSE" style="background:none">
    <img src="https://img.shields.io/badge/License-BSD-blue.svg?label=license">
  </a>
  <a target="_blank" href="https://github.com/caktus/dsd-pythonanywhere/actions/workflows/tests.yaml" style="background:none">
    <img src="https://github.com/caktus/dsd-pythonanywhere/actions/workflows/tests.yaml/badge.svg?branch=main">
  </a>
</div>

A plugin for deploying Django projects to [PythonAnywhere](https://www.pythonanywhere.com/), using django-simple-deploy.

For full documentation, see the documentation for [django-simple-deploy](https://django-simple-deploy.readthedocs.io/en/latest/).

**Current status:** In active development. Not yet recommended for actual
deployments yet.

- [Motivation](#motivation)
- [Quickstart](#quickstart)
- [Approach](#approach)
- [Plugin Development](#plugin-development)
  - [Automated Tests](#automated-tests)
  - [Releasing](#releasing)

## Motivation

This plugin hopes to provide a deployment option for `django-simple-deploy` that
doesn't require a credit card to get started. PythonAnywhere offers a free tier
that allows users to deploy small Django apps and may be a helpful way to get
small Django apps online without financial commitment.

## Quickstart

Deployment to [PythonAnywhere](https://www.pythonanywhere.com/) with this plugin
requires a few prerequisites:

- You must use Git to track your project and push your code to a remote
  repository (e.g. GitHub, GitLab, Bitbucket).
- You must track dependencies with a `requirements.txt` file.
- Create a PythonAnywhere [Beginner account](https://www.pythonanywhere.com/registration/register/beginner/),
  which is a limited account with one web app, but requires no credit card.
- Generate an [API token](https://help.pythonanywhere.com/pages/GettingYourAPIToken)
- Stay logged in to PythonAnywhere in your default browser.

With those prerequisites met, and if you're coming from the [Django Girls tutorial Deploy section](https://tutorial.djangogirls.org/en/deploy/),
you can deploy your project with the following steps:

1. Export your PythonAnywhere API credentials and install `dsd-pythonanywhere`:

```sh
# Export your PythonAnywhere API credentials as environment variables
export API_USER=[your_pythonanywhere_username]
export API_TOKEN=[your_pythonanywhere_api_token]
# Install dsd-pythonanywhere (which also installs django-simple-deploy)
pip install dsd-pythonanywhere
```

2. Add `django-simple-deploy` to your `INSTALLED_APPS` in `settings.py`:

```diff
diff --git a/mysite/settings.py b/mysite/settings.py
index 8bf8f39..b288aa1 100644
--- a/mysite/settings.py
+++ b/mysite/settings.py
@@ -38,6 +38,7 @@ INSTALLED_APPS = [
     "django.contrib.messages",
     "django.contrib.staticfiles",
     "blog",
+    "django_simple_deploy",
 ]
```

3. Run the deployment command:

```sh
python manage.py deploy --automate-all
```

This command can take several minutes as it creates the web app, installs
dependencies, etc. You should see progress in your browser console on
PythonAnywhere as well.

If you run into issues and need to re-run the deployment, you may need to
reset your local and remote repositories to a clean state first:

```sh
# Stash any local changes
git stash --include-untracked
# Go back to step 2 since settings.py was reverted
```

## Approach

PythonAnywhere provides a
[`pa_autoconfigure_django.py`](https://github.com/pythonanywhere/helper_scripts/blob/master/scripts/pa_autoconfigure_django.py)
helper script, currently used in the [Django Girls
tutorial](https://tutorial.djangogirls.org/en/deploy/). However, it's designed
to run directly on PythonAnywhere, which presents challenges: using a web-based
console, changes not being committed/pushed to version control, etc.

This plugin integrates with `django-simple-deploy` to provide a more familiar
local workflow, though with some caveats due to free tier limitations (primarily
lack of SSH access and required browser interaction).

```mermaid
sequenceDiagram
    participant User as Local Machine
    participant Browser
    participant GitHub
    participant PA as PythonAnywhere

    User->>GitHub: Commit & push changes

    User->>PA: Bash Console API: create console
    User->>Browser: Open console URL
    Note over Browser,PA: Browser connection starts bash process

    User->>PA: Bash Console API: clone repo
    PA->>GitHub: git clone
    PA->>PA: Install dependencies & create .env

    User->>PA: Webapp API: create webapp
    User->>PA: Bash Console API: copy wsgi.py

    PA-->>User: 🎉 App deployed!
```

**Note:** Users should stay logged into PythonAnywhere in their default browser
during deployment.

Additionally:

* If a PythonAnywhere bash console isn't already running, the plugin will
programmatically open your browser to the console URL. This is required because
the PythonAnywhere API creates console objects but doesn't start the actual
process. Only connecting to the console in a browser will do that (per the [API
documentation](https://help.pythonanywhere.com/pages/API/#apiv0userusernameconsoles)).

## Plugin Development

To set up a development environment for working on this plugin alongside
`django-simple-deploy`, follow these steps. This will create a directory
structure that looks like this:

```sh
dsd-dev/
├── django-simple-deploy             # ← parent project needed to run integration tests
├── dsd-pythonanywhere               # ← our plugin development directory
└── dsd-dev-project_[random_string]  # ← sample project for testing deployments
```

1. Create a parent directory to hold your development work:

```sh
mkdir dsd-dev
cd dsd-dev/
```

2. Clone `dsd-pythonanywhere` for development:

```sh
# Clone dsd-pythonanywhere for development (and switch to branch being worked on)
git clone git@github.com:caktus/dsd-pythonanywhere.git
```

3. Clone `django-simple-deploy` and create the blog sample project

```sh
git clone git@github.com:django-simple-deploy/django-simple-deploy.git
cd django-simple-deploy/
# Builds a copy of the sample project in parent dir for testing (../dsd-dev-project_[random_string]/)
uv run python tests/e2e_tests/utils/build_dev_env.py
```

4. Setup the development environment:

```sh
cd ../
cd dsd-dev-project_[random_string]/
source .venv/bin/activate
# Install dsd-pythonanywhere plugin in editable mode
pip install -e "../dsd-pythonanywhere/[dev]"
```

Your development environment is now configured to use your local copy of
`django-simple-deploy` and the `dsd-pythonanywhere` plugin in editable mode.
Verify with:

```sh
pip show django_simple_deploy dsd_pythonanywhere | grep Editable
```

5. Create a [new public repository on GitHub](https://github.com/new).

6. Push the sample project to your new repository:

```sh
git remote add origin git@github.com:[your_github_username]/[your_new_repo_name].git
git branch -M main
git push -u origin main
```

7. Configure environment variables for PythonAnywhere API access:

```sh
export API_USER=[your_pythonanywhere_username]
export API_TOKEN=[your_pythonanywhere_api_token]
```

If desired, you can add these lines to a `.env` file in the parent directory to
more easily load them when working on the project:

```sh
source ../.env
```

8. You can now make changes to `dsd-pythonanywhere` in the cloned directory
and test them by running deployments from the sample project:

```sh
python manage.py deploy
# To reset your sample project to a clean state between tests
python ./reset_project.py
# (**CAUTION**) If using --automate-all, you may need to force push to reset the remote changes
git push origin main --force
```

9. (Optional) Forward local ports for script debugging on PythonAnywhere:

To debug `scripts/setup.sh` that's run on PythonAnywhere during deployment, you
can use a service like [ngrok](https://ngrok.com/) to expose your local
`dsd_pythonanywhere` development code to the remote environment. First, start ngrok to
forward a local port (e.g., `8000`):

```sh
# In a new terminal
ngrok http 8000 --url https://<your_ngrok_subdomain>.ngrok-free.app
```

Then run a local HTTP server to serve your `dsd_pythonanywhere` code:

```sh
# In another terminal in the dsd-pythonanywhere directory
uv run python -m http.server 8000
```

Finally, set the `REMOTE_SETUP_SCRIPT_URL` environment variable
in your sample project to point to the ngrok URL for `scripts/setup.sh`:

```sh
export REMOTE_SETUP_SCRIPT_URL="https://<your_ngrok_subdomain>.ngrok-free.app/scripts/setup.sh"
```

### Automated Tests

To run the unit tests for this plugin, run:

```sh
cd dsd-pythonanywhere/
uv run pytest
```

To run the integration tests (and unit tests), which exercise the mechanics of
`python manage.py deploy` locally without actually deploying to PythonAnywhere,
run:

```sh
cd django-simple-deploy/
# Install dsd-pythonanywhere plugin in editable mode
uv add --editable "../dsd-pythonanywhere[dev]"
uv run pytest
# To skip platform_agnostic_tests for faster feedback during plugin development:
uv run pytest --ignore=tests/integration_tests/platform_agnostic_tests
```

### Releasing

1. Bump the version in `pyproject.toml`:
   ```sh
   uv version --bump patch  # or --bump minor/major
   ```

2. Add release notes to `CHANGELOG.md`

3. Create a new release on GitHub:
   - Tag the version (e.g., `v0.2.1`)
   - Add the same release notes
   - Publish the release

   When the release is published, CI automatically builds and publishes the package to PyPI.

<!-- omit in toc -->
#### Test Release

If you're testing a release, you can use `test.pypi.org` with a command like:

```sh
op run --env-file ../.testpypi -- uv publish --publish-url https://test.pypi.org/legacy/ 
```
