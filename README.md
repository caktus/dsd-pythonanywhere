# dsd-pythonanywhere

A plugin for deploying Django projects to [PythonAnywhere](https://www.pythonanywhere.com/), using django-simple-deploy.

For full documentation, see the documentation for [django-simple-deploy](https://django-simple-deploy.readthedocs.io/en/latest/).

**Current status:** In active development. The plugin currently clones your
repository to PythonAnywhere, but it doesn't configure the web app just yet. Not
yet recommended for actual deployments yet.

## Motivation

This plugin is motivated by the desire to provide a deployment option for
`django-simple-deploy` that doesn't require a credit card to get started.
PythonAnywhere offers a free tier that allows users to deploy small Django apps
and may be a helpful way to get small Django apps online without financial
commitment.

## Quickstart

Deployment to [PythonAnywhere](https://www.pythonanywhere.com/) with this plugin
requires a few prerequisites:

- You must use Git to track your project and push your code to a remote
  repository (e.g. GitHub, GitLab, Bitbucket).
- You must track dependencies with a `requirements.txt` file.
- Create a PythonAnywhere [Beginner account](https://www.pythonanywhere.com/registration/register/beginner/),
  which is a limited account with one web app, but requires no credit card.
- Generate an [API token](https://help.pythonanywhere.com/pages/GettingYourAPIToken)
- Ideally, stay logged in to PythonAnywhere in your default browser to make the
  first deployment smoother.

## Plugin Development

To set up a development environment for working on this plugin alongside
`django-simple-deploy`, follow these steps.

1. Create a parent directory to hold your development work:

```sh
mkdir dsd-dev
cd dsd-dev/
```

2. Clone `dsd-pythonanywhere` for development:

```sh
# Clone dsd-pythonanywhere for development (and switch to branch being worked on)
git clone git@github.com:caktus/dsd-pythonanywhere.git --branch add-api-client
```

3. Clone `django-simple-deploy` and create the blog sample project

```sh
git clone git@github.com:django-simple-deploy/django-simple-deploy.git
cd django-simple-deploy/
# Builds a copy of the sample project in parent dir for testing (../dsd-dev-project-[random_string]/)
uv run python tests/e2e_tests/utils/build_dev_env.py
```

4. Setup the development environment:

```sh
cd ../
cd dsd-dev-project-[random_string]/
source .venv/bin/activate
# Install dsd-pythonanywhere plugin in editable mode
pip install -e "../dsd-pythonanywhere/[dev]"
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

8. You can now make changes to `dsd-pythonanywhere` in the cloned directory
and test them by running deployments from the sample project:

```sh
python manage.py deploy
```
