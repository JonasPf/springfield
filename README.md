# Springfield - Where Ralph lives

A containerized dev environment built on Ubuntu 24.04 and Podman. You get a consistent, isolated workspace for each project without polluting your host machine.

## What's in the box

Baked into the image: Go 1.23.6, Node.js 22 LTS + npm, Make, Vim, Fish shell (default), bat, git, curl, wget, jq, sudo.

Installed on first boot: Claude Code.

## Quick start

```bash
# Build the image once
podman build -t springfield .

# Launch from any project directory
/path/to/springfield.sh
```

The idea is one container per project. Run `springfield.sh` from `~/work/api` and you get a container named `work-api` with its own persistent home directory. Run it from `~/work/frontend` and you get `work-frontend`. Each container mounts its project directory at `/work` and keeps its home state in `~/.springfield/{rel_path}/ralphhome`, so your project directories stay clean and containers don't step on each other.

You can run as many of these in parallel as you want — each project gets its own isolated environment with its own shell history, editor state, and port mappings. Running `springfield.sh` again from the same directory opens another shell into the same container, so you can split panes in iTerm2 and have multiple terminals in the same project environment.

## How it works

**`springfield.sh`** — The host-side launcher. Starts a new container or reattaches to an existing one. Handles home directory setup, port forwarding (prompted on first run, saved for next time), timezone passthrough, and container naming.

**`entrypoint.sh`** — Runs as root on container boot to match `ralph`'s UID/GID to the host user, kicks off first-run setup if needed, then drops privileges.

**`setup.sh`** — Runs once on first boot as `ralph`. Copies `homefiles/` into `$HOME/`, installs Claude Code, and writes a lock file. Delete `~/.setup_done` and re-run it to reset.

**`homefiles/`** — A template of `/home/ralph`, copied in on first boot. Fish and Vim config, git identity, Claude Code settings.

## Session viewer

`viewer.py` serves a local web UI (`viewer.html`) for browsing Claude Code chat sessions stored in `~/.springfield/`. Run it on the host, not inside a Springfield container, and open the printed URL — it discovers all projects, lists sessions by recency, and lets you read through conversations with syntax-highlighted tool calls and thinking blocks.

## Make it yours

This is opinionated — it's my setup. Fork it and change whatever you want:

- **`homefiles/`** — Shell config, editor settings, git identity, anything you want in `$HOME`.
- **`Dockerfile`** — System packages, base image, language runtimes.
- **`setup.sh`** — What gets installed on first boot.
