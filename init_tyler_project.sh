#!/bin/bash

# Get the directory where this script is located (Tyler source directory)
TYLER_SOURCE_DIR="$(pwd)"
PARENT_DIR="$(dirname "$TYLER_SOURCE_DIR")"
NEW_PROJECT_DIR="$PARENT_DIR/tyler-examples"

# Create new project directory
echo "Creating new project directory at $NEW_PROJECT_DIR..."
mkdir -p "$NEW_PROJECT_DIR"
cd "$NEW_PROJECT_DIR"

# Set up Python environment
echo "Setting up Python environment..."
if [ ! -f .python-version ]; then
    echo "tyler-examples" > .python-version
    pyenv virtualenv 3.12.8 tyler-examples || { echo "Failed to create virtualenv"; exit 1; }
fi

# Activate the virtual environment
eval "$(pyenv init -)"
eval "$(pyenv virtualenv-init -)"
pyenv activate tyler-examples

# Install Tyler in development mode using uv
echo "Installing Tyler in development mode..."
uv add --dev --editable "$TYLER_SOURCE_DIR"

# Copy example files directly to root
echo "Copying example files..."
cp "$TYLER_SOURCE_DIR/examples/basic.py" ./
cp "$TYLER_SOURCE_DIR/examples/database_storage.py" ./
cp "$TYLER_SOURCE_DIR/examples/memory_storage.py" ./

# Create .env file
echo "Creating .env file..."
if [ ! -f .env ]; then
    cp "$TYLER_SOURCE_DIR/.env.example" .env
    echo "Please edit .env file with your API keys and configuration"
fi

echo "Project initialization complete!"
echo "Next steps:"
echo "1. Edit .env file with your API keys"
echo "2. Run examples with:"
echo "   uv run python basic.py"
echo "   uv run python memory_storage.py"
echo "   uv run python database_storage.py" 