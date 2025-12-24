#!/bin/bash
# setup.sh - Setup environment using Poetry (modern approach)
set -e

echo "🚀 Setting up Python environment with Poetry..."

# Check if Poetry is installed
if ! command -v poetry &> /dev/null; then
    echo "❌ Poetry not found. Installing via Homebrew..."
    if command -v brew &> /dev/null; then
        brew install poetry
    else
        echo "⚠️  Homebrew not found. Install Poetry manually:"
        echo "   curl -sSL https://install.python-poetry.org | python3 -"
        exit 1
    fi
fi

# Install dependencies
poetry install

echo ""
echo "🎉 Setup complete!"
echo ""
echo "To activate the environment, run:"
echo "  poetry shell"
echo ""
echo "Or run commands directly with:"
echo "  poetry run python rsync_restore.py --help"
echo "  poetry run pytest tests/"
