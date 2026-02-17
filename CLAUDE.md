# Springfield

## Project overview

This project defines a Docker/Podman-based development container ("Springfield") built on Ubuntu 24.04. It provides a consistent, reproducible development environment with common tools pre-installed. The container user is `ralph`.

## Architecture

### Dockerfile

Builds the `springfield` image. Installs system packages as root, then creates a non-root `ralph` user. The `homefiles/` directory is copied to `/opt/homefiles/` in the image. Tooling that changes frequently (Claude Code, spec-kit) is installed at first run by `setup.sh`, not baked into the image.

### setup.sh

First-run script, executed as `ralph` inside the container on initial boot. Does:
- Copies homefiles from `/opt/homefiles/` to `$HOME/`
- Installs Claude Code via the official installer
- Creates `$HOME/.setup_done` lock file to prevent re-running

Can also be run manually inside the container to re-run setup.

### homefiles/

Mirrors the `/home/ralph` home directory layout exactly. Everything in here is copied verbatim to `/home/ralph` on first run by `setup.sh`. To update homefiles in a running container, re-run `setup.sh`.

### entrypoint.sh

Container entrypoint. Runs as root: adjusts `ralph`'s UID/GID to match the host, then checks for `$HOME/.setup_done` — if missing, runs `setup.sh` via `setpriv`. Passes through to the CMD (`fish`).

### springfield.sh

Host-side launcher script. Run from a project directory to start the container. Manages:
- Centralized home directory at `~/.springfield/{rel_path}/ralphhome`
- Port forwarding config (interactive prompt, saved to `~/.springfield/{rel_path}/containerconfig.json`)
- Deterministic container names derived from project path relative to `$HOME`
- Timezone passthrough from host
- Container invocation via `podman run`

### vimrc

Vim configuration copied into the image. Requires `~/.vim/{backup,swp,undo}` directories (created by `setup.sh` via homefiles).

## Container runtime

- Image name: `springfield`
- Container runtime: `podman`
- User inside container: `ralph` (non-root, passwordless sudo)
- Default shell: fish (with vim keybindings)
- Home directory: `/home/ralph` (mounted from `~/.springfield/{rel_path}/ralphhome`)
- Project mount: `/work`

## Installed tools

Go, Node.js + npm, Make, Vim, bat (aliased from `batcat`), Fish shell, git, curl, wget, jq, sudo.

Tools installed at first run (by `setup.sh`): Claude Code.
