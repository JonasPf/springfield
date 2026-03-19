#!/bin/bash
# Host-side launcher. Run from a project directory to start a Springfield container.
# Manages per-project home directories and container lifecycle.
set -e

IMAGE="springfield"
WORKDIR="$(pwd)"

usage() {
    echo "Usage: springfield.sh [OPTIONS]"
    echo ""
    echo "Launch a Springfield dev container for the current project directory."
    echo ""
    echo "Options:"
    echo "  -h, --help   Show this help message"
    exit 0
}

for arg in "$@"; do
    case "$arg" in
        -h|--help)   usage ;;
        *)           echo "❌ Unknown option: $arg"; usage ;;
    esac
done

# --- Derive names and paths ---
REL_PATH="${WORKDIR#"$HOME/"}"
REL_PATH="${REL_PATH#/}"
CONTAINER_NAME="$(echo "$REL_PATH" | tr '/' '-' | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9._-]/-/g')"

SPRINGFIELD_DIR="$HOME/.springfield/$REL_PATH"
RALPH_HOME="$SPRINGFIELD_DIR/ralphhome"

# --- Attach to running container if one exists ---
RUNNING=$(podman ps --filter "label=springfield.workdir=$WORKDIR" --format "{{.Names}}" 2>/dev/null | head -1)
if [ -n "$RUNNING" ]; then
    echo "🔗 Attaching to running container: $RUNNING"
    exec podman exec -it --user ralph "$RUNNING" fish
fi

# --- Create home directory and shared directory ---
mkdir -p "$RALPH_HOME"
SHARED_DIR="$HOME/.springfield/shared"
mkdir -p "$SHARED_DIR"

# --- Timezone passthrough ---
TZ_FLAGS=""
if [ -n "$TZ" ]; then
    TZ_FLAGS="-e TZ=$TZ"
fi
if [ -f /etc/localtime ]; then
    TZ_FLAGS="$TZ_FLAGS -v /etc/localtime:/etc/localtime:ro"
fi

# --- Launch ---
echo "🚀 Starting container: $CONTAINER_NAME"
# Disable SELinux labeling so the container can access the host Podman socket
exec podman run -it --rm \
    --name "$CONTAINER_NAME" \
    --hostname "$(basename "$WORKDIR")" \
    --label "springfield.workdir=$WORKDIR" \
    --network=host \
    $TZ_FLAGS \
    -e HOST_UID="$(id -u)" \
    -e HOST_GID="$(id -g)" \
    --security-opt label=disable \
    -v "/run/user/$(id -u)/podman/podman.sock:/var/run/docker.sock" \
    -v "$WORKDIR:/work" \
    -v "$RALPH_HOME:/home/ralph" \
    -v "$SHARED_DIR:/home/ralph/shared" \
    -w /work \
    "$IMAGE"
