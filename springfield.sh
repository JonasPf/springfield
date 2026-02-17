#!/bin/bash
# Host-side launcher. Run from a project directory to start a Springfield container.
# Manages per-project home directories, port forwarding, and container lifecycle.
set -e

IMAGE="springfield"
WORKDIR="$(pwd)"

# --- Flags ---
SKIP_PORTS=false
RESET_CONFIG=false

usage() {
    echo "Usage: springfield.sh [OPTIONS]"
    echo ""
    echo "Launch a Springfield dev container for the current project directory."
    echo ""
    echo "Options:"
    echo "  --no-ports   Skip port forwarding entirely"
    echo "  --reset      Delete saved port config and re-prompt"
    echo "  -h, --help   Show this help message"
    echo ""
    echo "Config is stored in ~/.springfield/<project>/containerconfig.json"
    exit 0
}

for arg in "$@"; do
    case "$arg" in
        --no-ports)  SKIP_PORTS=true ;;
        --reset)     RESET_CONFIG=true ;;
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
CONFIG="$SPRINGFIELD_DIR/containerconfig.json"

# --- Attach to running container if one exists ---
RUNNING=$(podman ps --filter "label=springfield.workdir=$WORKDIR" --format "{{.Names}}" 2>/dev/null | head -1)
if [ -n "$RUNNING" ]; then
    echo "🔗 Attaching to running container: $RUNNING"
    exec podman exec -it --user ralph "$RUNNING" fish
fi

# --- Create home directory ---
mkdir -p "$RALPH_HOME"

# --- Port configuration ---
if [ "$RESET_CONFIG" = true ] && [ -f "$CONFIG" ]; then
    rm "$CONFIG"
    echo "🔧 Port config reset."
fi

PORT_FLAGS=""
if [ "$SKIP_PORTS" = false ]; then
    if [ -f "$CONFIG" ]; then
        PORTS=$(jq -r '.ports // [] | .[]' "$CONFIG")
        if [ -n "$PORTS" ]; then
            echo "📡 Saved ports: $(echo "$PORTS" | tr '\n' ' ')"
        else
            echo "📡 No ports configured."
        fi
        echo -n "Keep this config? [Y/n] "
        read -r answer
        if [[ "$answer" =~ ^[Nn] ]]; then
            rm "$CONFIG"
        fi
    fi

    if [ ! -f "$CONFIG" ]; then
        echo -n "📡 Ports to forward (comma-separated, or empty for none): "
        read -r port_input
        IFS=', ' read -ra PORT_ARRAY <<< "$port_input"
        jq -n --argjson ports "$(printf '%s\n' "${PORT_ARRAY[@]}" | jq -R 'select(length > 0) | tonumber' | jq -s '.')" \
            '{ports: $ports}' > "$CONFIG"
    fi

    PORTS=$(jq -r '.ports // [] | .[]' "$CONFIG")
    while IFS= read -r port; do
        [ -n "$port" ] && PORT_FLAGS="$PORT_FLAGS -p $port:$port"
    done <<< "$PORTS"
else
    echo "📡 Skipping port forwarding."
fi

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
exec podman run -it --rm \
    --name "$CONTAINER_NAME" \
    --hostname "$(basename "$WORKDIR")" \
    --label "springfield.workdir=$WORKDIR" \
    $PORT_FLAGS \
    $TZ_FLAGS \
    -e HOST_UID="$(id -u)" \
    -e HOST_GID="$(id -g)" \
    -v "$WORKDIR:/work" \
    -v "$RALPH_HOME:/home/ralph" \
    -w /work \
    "$IMAGE"
