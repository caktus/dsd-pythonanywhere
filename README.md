# dsd-pythonanywhere

A plugin for deploying Django projects to PythonAnywhere, using django-simple-deploy.

For full documentation, see the documentation for [django-simple-deploy](https://django-simple-deploy.readthedocs.io/en/latest/).

## Plugin Development

To set up a development environment for working on this plugin alongside `django-simple-deploy`, follow these steps:

```sh
# Create parent dir to hold development work
mkdir dsd-dev
cd dsd-dev/

# Clone dsd-pythonanywhere for development
git clone git@github.com:caktus/dsd-pythonanywhere.git
cd dsd-pythonanywhere/
git checkout add-api-client  # switch to branch being worked on

# Clone django-simple-deploy and set up development environment
cd ..
git clone git@github.com:django-simple-deploy/django-simple-deploy.git
cd django-simple-deploy/
uv venv --python 3.12
uv pip install -e ".[dev]"
uv pip install -e "../dsd-pythonanywhere/[dev]"
uv run pytest tests/unit_tests
```
