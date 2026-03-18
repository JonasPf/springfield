#!/bin/bash
# Runs as root. Adjusts ralph's UID/GID to match the host,
# triggers first-run setup if needed, then drops to ralph.

USERNAME="ralph"
TARGET_UID="${HOST_UID:-1000}"
TARGET_GID="${HOST_GID:-1000}"
CURRENT_UID=$(id -u "$USERNAME")
CURRENT_GID=$(id -g "$USERNAME")

if [ "$TARGET_GID" != "$CURRENT_GID" ]; then
    echo "🔧 Adjusting GID: $CURRENT_GID → $TARGET_GID"
    groupmod -g "$TARGET_GID" "$USERNAME" 2>/dev/null || groupmod -o -g "$TARGET_GID" "$USERNAME"
fi

if [ "$TARGET_UID" != "$CURRENT_UID" ]; then
    echo "🔧 Adjusting UID: $CURRENT_UID → $TARGET_UID"
    usermod -u "$TARGET_UID" "$USERNAME"
fi

export HOME="/home/$USERNAME"
chown -R "$TARGET_UID:$TARGET_GID" "$HOME"

# Fix Docker socket permissions if mounted
if [ -S /var/run/docker.sock ]; then
    chmod 660 /var/run/docker.sock
    chgrp docker /var/run/docker.sock
fi

# First-run setup (homefiles, Claude Code, spec-kit)
if [ ! -f "$HOME/.setup_done" ]; then
    echo "🚀 First run detected — running setup..."
    setpriv --reuid="$TARGET_UID" --regid="$TARGET_GID" --init-groups setup.sh
else
    echo "✅ Setup already done, starting shell."
fi

exec setpriv --reuid="$TARGET_UID" --regid="$TARGET_GID" --init-groups "$@"
