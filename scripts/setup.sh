#!/bin/bash
set -e

if [ -z "$1" ] || [ -z "$2" ]; then
	echo "Usage: $0 <git-repo-url> <directory-name>"
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
	python3.12 -m venv venv
fi

echo "Activating virtual environment..."
source venv/bin/activate

echo "Installing dependencies..."

./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r $2/requirements.txt
