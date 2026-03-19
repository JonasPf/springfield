#!/bin/bash
# Forward ports from macOS to the Podman VM so services running inside
# Springfield (--network=host) are accessible on the Mac.
#
# Usage: springfield-forward.sh 5432 8080 3000
#        springfield-forward.sh --stop
set -e

if [ $# -eq 0 ]; then
    echo "Usage: springfield-forward.sh PORT [PORT...]"
    echo "       springfield-forward.sh --stop"
    echo ""
    echo "Forward ports from macOS through the Podman VM."
    echo "Press Ctrl-C or use --stop to tear down all forwards."
    exit 0
fi

PIDFILE="$HOME/.springfield/forward.pid"

if [ "$1" = "--stop" ]; then
    if [ -f "$PIDFILE" ]; then
        kill "$(cat "$PIDFILE")" 2>/dev/null && echo "Stopped port forwarding." || echo "No active forwarding found."
        rm -f "$PIDFILE"
    else
        echo "No active forwarding found."
    fi
    exit 0
fi

# Get SSH connection details from podman machine
SSH_PORT=$(podman machine inspect | jq -r '.[0].SSHConfig.Port')
SSH_KEY=$(podman machine inspect | jq -r '.[0].SSHConfig.IdentityPath')
SSH_USER=$(podman machine inspect | jq -r '.[0].SSHConfig.RemoteUsername')

if [ -z "$SSH_PORT" ] || [ "$SSH_PORT" = "null" ]; then
    echo "❌ Could not get SSH details from podman machine inspect"
    exit 1
fi

# Build -L flags for each port
SSH_FLAGS=""
for port in "$@"; do
    SSH_FLAGS="$SSH_FLAGS -L localhost:${port}:localhost:${port}"
    echo "📡 Forwarding localhost:${port}"
done

# Stop any existing forwards
if [ -f "$PIDFILE" ]; then
    kill "$(cat "$PIDFILE")" 2>/dev/null || true
    rm -f "$PIDFILE"
fi

mkdir -p "$HOME/.springfield"
echo "Press Ctrl-C to stop forwarding."
ssh -i "$SSH_KEY" -p "$SSH_PORT" \
    $SSH_FLAGS \
    -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=/dev/null \
    -N "$SSH_USER@localhost" &
PID=$!
echo "$PID" > "$PIDFILE"

cleanup() {
    kill "$PID" 2>/dev/null || true
    rm -f "$PIDFILE"
    echo ""
    echo "Stopped port forwarding."
}
trap cleanup EXIT INT TERM

wait "$PID"
