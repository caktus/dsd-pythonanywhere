#!/bin/bash
set -e

if [ -z "$1" ] || [ -z "$2" ] || [ -z "$3" ]; then
	echo "Usage: $0 <git-repo-url> <directory-name> <django-project-name> [python-version]"
	exit 1
fi

GIT_REPO_URL=$1
REPO_NAME=$2
DJANGO_PROJECT_NAME=$3
PYTHON_VERSION=${4:-python3.13}

# Clone the repository from the provided Git URL

echo "Cloning repository..."

if [ ! -d "$REPO_NAME" ]; then
	git clone "$GIT_REPO_URL" "$REPO_NAME"
else
	echo "Directory $REPO_NAME already exists. Skipping clone."
fi

# Create and activate a Python virtual environment, if it doesn't already exist

echo "Setting up Python virtual environment..."

if [ ! -d "venv" ]; then
	echo "Creating virtual environment..."
	$PYTHON_VERSION -m venv venv
fi

echo "Activating virtual environment..."
source venv/bin/activate

echo "Installing dependencies..."

./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r $REPO_NAME/requirements.txt

# Create .env file with environment variables

echo "Creating .env file..."

if [ ! -f "$REPO_NAME/.env" ]; then
	# Generate a random Django secret key
	DJANGO_SECRET_KEY=$(./venv/bin/python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")
	cat > "$REPO_NAME/.env" << EOF
DEBUG=TRUE
ON_PYTHONANYWHERE=TRUE
SECRET_KEY=$DJANGO_SECRET_KEY
DATABASE_URL=sqlite:///$HOME/$REPO_NAME/db.sqlite3
EOF
	echo ".env file created."
else
	echo ".env file already exists. Skipping creation."
fi

# Run migrations and collectstatic
echo "Running migrations and collectstatic..."
cd "$REPO_NAME"
../venv/bin/python manage.py migrate
../venv/bin/python manage.py collectstatic --noinput

echo "Setup complete!!!"
