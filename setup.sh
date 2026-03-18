#!/bin/bash
# First-run setup script. Runs as ralph inside the container.
# Installs homefiles, Claude Code, and spec-kit, then creates a lock file.
set -e

export PATH="$HOME/.local/bin:$PATH"

LOCK="$HOME/.setup_done"

if [ -f "$LOCK" ]; then
    echo "✅ Setup already completed. Delete $LOCK to re-run."
    exit 0
fi

echo "🚀 Running first-time setup..."

# Homefiles
echo "📂 Installing homefiles..."
cp -a /opt/homefiles/. "$HOME/"
echo "✅ Homefiles installed."

# Claude Code
echo "🤖 Installing Claude Code..."
curl -fsSL https://claude.ai/install.sh | bash
echo "✅ Claude Code installed to /opt/claude."

# Done
touch "$LOCK"
echo "🎉 Setup complete!"
