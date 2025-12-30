#!/bin/bash
set -e

if [ -z "$1" ] || [ -z "$2" ]; then
	echo "Usage: $0 <git-repo-url> <directory-name> <python-version>"
	exit 1
fi

# Clone the repository from the provided Git URL

echo "Cloning repository..."

if [ ! -d "$2" ]; then
	git clone "$1" "$2"
else
	echo "Directory $2 already exists. Skipping clone."
fi

# Create and activate a Python virtual environment, if it doesn't already exist

echo "Setting up Python virtual environment..."

if [ ! -d "venv" ]; then
	echo "Creating virtual environment..."
	${3:-python3.13} -m venv venv
fi

echo "Activating virtual environment..."
source venv/bin/activate

echo "Installing dependencies..."

./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r $2/requirements.txt

# Create .env file with environment variables

echo "Creating .env file..."

if [ ! -f "$2/.env" ]; then
	# Generate a random Django secret key
	DJANGO_SECRET_KEY=$(./venv/bin/python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")
	cat > "$2/.env" << EOF
DEBUG=TRUE
ON_PYTHONANYWHERE=TRUE
SECRET_KEY=$DJANGO_SECRET_KEY
EOF
	echo ".env file created."
else
	echo ".env file already exists. Skipping creation."
fi

echo "Setup complete!!!"
