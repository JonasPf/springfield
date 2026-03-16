#!/usr/bin/env python3
"""Ralph Wiggum Loop — Python implementation.

Drives Claude Code in a loop, feeding it a prompt file each iteration.
Supports plan mode (generate/update IMPLEMENTATION_PLAN.md) and build mode
(implement from plan, commit, repeat).

Usage:
    loop.py [plan|build] [OPTIONS]
    loop.py --help
"""

import argparse
import json
import os
import re
import subprocess
import sys
import textwrap
import time
from pathlib import Path

# ─── Constants ────────────────────────────────────────────────────────────────

PLAN_PROMPT = "PROMPT_plan.md"
BUILD_PROMPT = "PROMPT_build.md"
IMPLEMENTATION_PLAN = "IMPLEMENTATION_PLAN.md"

PLAN_DEFAULT_ITERATIONS = 20
BUILD_DEFAULT_ITERATIONS = 0  # unlimited

# ─── Prompt templates ────────────────────────────────────────────────────────

BUILD_PROMPT_TEMPLATE = """\
0a. Study `specs/*` with up to 500 parallel Sonnet subagents to learn the application specifications.
0b. Study @IMPLEMENTATION_PLAN.md.

1. Your task is to implement functionality per the specifications using parallel subagents. Follow @IMPLEMENTATION_PLAN.md and choose the most important unchecked item to address. Before making changes, search the codebase (don't assume not implemented) using Sonnet subagents. You may use up to 500 parallel Sonnet subagents for searches/reads and only 1 Sonnet subagent for build/tests. Use Opus subagents when complex reasoning is needed (debugging, architectural decisions).
2. After implementing functionality or resolving problems, run the tests for that unit of code that was improved. If functionality is missing then it's your job to add it as per the application specifications. Ultrathink.
3. When you discover issues, immediately update @IMPLEMENTATION_PLAN.md with your findings using a subagent. When resolved, check off the item with [x].
4. When the tests pass, update @IMPLEMENTATION_PLAN.md (check off completed items), then `git add -A` then `git commit` with a message describing the changes. Do NOT push to a remote.

99999. Important: When authoring documentation, capture the why — tests and implementation importance.
999999. Important: Single sources of truth, no migrations/adapters. If tests unrelated to your work fail, resolve them as part of the increment.
9999999. As soon as there are no build or test errors create a git tag. If there are no git tags start at 0.0.0 and increment patch by 1 for example 0.0.1 if 0.0.0 does not exist.
99999999. You may add extra logging if required to debug issues.
999999999. Keep @IMPLEMENTATION_PLAN.md current with learnings using a subagent — future work depends on this to avoid duplicating efforts. Update especially after finishing your turn. Use checkbox format: - [ ] for pending, - [x] for done.
9999999999. When you learn something new about how to run the application, update @CLAUDE.md using a subagent but keep it brief. For example if you run commands multiple times before learning the correct command then that file should be updated.
99999999999. For any bugs you notice, resolve them or document them in @IMPLEMENTATION_PLAN.md using a subagent even if it is unrelated to the current piece of work.
999999999999. Implement functionality completely. Placeholders and stubs waste efforts and time redoing the same work.
9999999999999. When @IMPLEMENTATION_PLAN.md becomes large periodically clean out the items that are completed from the file using a subagent.
99999999999999. If you find inconsistencies in the specs/* then use an Opus subagent with 'ultrathink' requested to update the specs.
999999999999999. IMPORTANT: Keep @CLAUDE.md operational only — status updates and progress notes belong in `IMPLEMENTATION_PLAN.md`. A bloated CLAUDE.md pollutes every future loop's context.
"""

PLAN_PROMPT_TEMPLATE = """\
0a. Study `specs/*` with up to 250 parallel Sonnet subagents to learn the application specifications.
0b. Study @IMPLEMENTATION_PLAN.md (if present) to understand the plan so far.

1. Study @IMPLEMENTATION_PLAN.md (if present; it may be incorrect) and use up to 500 Sonnet subagents to study existing source code and compare it against `specs/*`. Use an Opus subagent to analyze findings, prioritize tasks, and create/update @IMPLEMENTATION_PLAN.md as a checkbox list sorted in priority of items yet to be implemented. Use `- [ ]` for pending items and `- [x]` for completed items. Ultrathink. Consider searching for TODO, minimal implementations, placeholders, skipped/flaky tests, and inconsistent patterns. Study @IMPLEMENTATION_PLAN.md to determine starting point for research and keep it up to date with items considered complete/incomplete using subagents.

IMPORTANT: Plan only. Do NOT implement anything. Do NOT assume functionality is missing; confirm with code search first.

IMPORTANT: The implementation plan MUST use markdown checkbox syntax for every task item:
- `- [ ]` for items not yet implemented
- `- [x]` for items that are complete
This format is required so that loop.py can parse progress automatically.

ULTIMATE GOAL: Study the specs/* and codebase to produce a comprehensive, prioritized implementation plan. If a specification is missing, search first to confirm it doesn't exist, then if needed author it at specs/FILENAME.md. If you create a new specification then document the plan to implement it in @IMPLEMENTATION_PLAN.md using a subagent.
"""

# ─── Terminal helpers ─────────────────────────────────────────────────────────

BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"
RESET = "\033[0m"


def _supports_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


COLOR = _supports_color()


def c(code: str, text: str) -> str:
    return f"{code}{text}{RESET}" if COLOR else text


def banner(text: str) -> None:
    width = max(len(text) + 4, 50)
    print()
    print(c(CYAN, "=" * width))
    print(c(CYAN, f"  {text}"))
    print(c(CYAN, "=" * width))
    print()


def info(msg: str) -> None:
    print(f"  {c(BLUE, '>')} {msg}")


def success(msg: str) -> None:
    print(f"  {c(GREEN, '+')} {msg}")


def warn(msg: str) -> None:
    print(f"  {c(YELLOW, '!')} {msg}")


def error(msg: str) -> None:
    print(f"  {c(RED, 'x')} {msg}")


def section(title: str) -> None:
    print()
    print(f"  {c(BOLD, title)}")
    print(f"  {c(DIM, '-' * len(title))}")


# ─── Precondition checks ─────────────────────────────────────────────────────


def check_git_repo() -> bool:
    """Verify we are inside a git repository."""
    result = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        capture_output=True, text=True,
    )
    return result.returncode == 0


def check_clean_worktree() -> bool:
    """Return True if there are no uncommitted or unstaged changes."""
    # Check for staged changes
    staged = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        capture_output=True,
    )
    # Check for unstaged changes
    unstaged = subprocess.run(
        ["git", "diff", "--quiet"],
        capture_output=True,
    )
    # Check for untracked files
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        capture_output=True, text=True,
    )

    clean = staged.returncode == 0 and unstaged.returncode == 0 and not untracked.stdout.strip()

    if not clean:
        if staged.returncode != 0:
            warn("There are staged (uncommitted) changes")
        if unstaged.returncode != 0:
            warn("There are unstaged modifications")
        if untracked.stdout.strip():
            warn("There are untracked files:")
            for f in untracked.stdout.strip().splitlines()[:10]:
                print(f"      {c(DIM, f)}")

    return clean


def check_auto_compact() -> bool:
    """Return True if auto-compact is disabled (safe to proceed).

    Checks ~/.claude.json for autoCompactEnabled. When false, auto-compact
    is disabled. Any other value (or missing key) means it's enabled and
    will interfere with the loop.
    """
    path = Path.home() / ".claude.json"
    try:
        data = json.loads(path.read_text())
        if data.get("autoCompactEnabled") is False:
            return True
    except (json.JSONDecodeError, OSError, FileNotFoundError):
        pass

    error("Auto-compact is enabled (or not explicitly disabled)")
    print()
    info("Auto-compact interferes with the ralph wiggum loop by")
    info("compacting context mid-iteration, which can cause the")
    info("agent to lose track of what it was doing.")
    print()
    info("Disable it by running:")
    print(f"      {c(BOLD, 'claude config set autoCompact false')}")
    print()
    return False


def check_auto_memory() -> bool:
    """Return True if auto-memory is disabled (safe to proceed).

    autoMemoryEnabled defaults to true. It must be explicitly set to
    false to prevent Claude from writing memory files mid-iteration,
    which pollutes context.
    """
    settings_paths = [
        Path.home() / ".claude" / "settings.json",
        Path.home() / ".claude.json",
    ]

    project_settings = Path(".claude") / "settings.json"
    if project_settings.exists():
        settings_paths.insert(0, project_settings)

    for path in settings_paths:
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text())
            if "autoMemoryEnabled" not in data:
                continue
            if data["autoMemoryEnabled"] is False:
                return True
            error(f"Auto-memory is enabled in {path}")
            print()
            info("Auto-memory pollutes the loop context by writing")
            info("memory files mid-iteration.")
            print()
            info("Disable it by running:")
            print(f"      {c(BOLD, 'claude config set autoMemoryEnabled false')}")
            print()
            return False
        except (json.JSONDecodeError, OSError):
            continue

    # Not set anywhere — defaults to enabled
    error("Auto-memory is not explicitly disabled (defaults to enabled)")
    print()
    info("Auto-memory pollutes the loop context by writing")
    info("memory files mid-iteration.")
    print()
    info("Disable it by running:")
    print(f"      {c(BOLD, 'claude config set autoMemoryEnabled false')}")
    print()
    return False


def check_prompt_file(prompt_file: str) -> bool:
    """Verify the prompt file exists."""
    if not Path(prompt_file).exists():
        error(f"Prompt file not found: {prompt_file}")
        info("Expected file in the current directory.")
        return False
    return True


# ─── Plan parsing ─────────────────────────────────────────────────────────────


def parse_plan_tasks(path: str = IMPLEMENTATION_PLAN) -> dict:
    """Parse IMPLEMENTATION_PLAN.md and return task statistics.

    Returns dict with keys: total, done, pending, tasks (list of dicts).
    Tasks are identified by markdown checkbox syntax: - [ ] or - [x].
    """
    result = {"total": 0, "done": 0, "pending": 0, "tasks": []}

    plan_path = Path(path)
    if not plan_path.exists():
        return result

    text = plan_path.read_text()
    for line in text.splitlines():
        stripped = line.strip()
        # Match markdown checkboxes:  - [ ] task  or  - [x] task  or  * [x] task
        m = re.match(r'^[-*]\s+\[([ xX])\]\s+(.*)', stripped)
        if m:
            checked = m.group(1).lower() == 'x'
            task_text = m.group(2).strip()
            result["total"] += 1
            if checked:
                result["done"] += 1
            else:
                result["pending"] += 1
            result["tasks"].append({"text": task_text, "done": checked})

    return result


def print_plan_summary(tasks: dict) -> None:
    """Print a human-readable summary of the implementation plan."""
    if tasks["total"] == 0:
        info("No tasks found in IMPLEMENTATION_PLAN.md")
        return

    pct = (tasks["done"] / tasks["total"]) * 100 if tasks["total"] > 0 else 0
    bar_width = 30
    filled = int(bar_width * tasks["done"] / tasks["total"])
    bar = c(GREEN, "#" * filled) + c(DIM, "-" * (bar_width - filled))

    info(f"Progress: [{bar}] {pct:.0f}%")
    info(f"Tasks: {c(GREEN, str(tasks['done']))} done / {c(YELLOW, str(tasks['pending']))} pending / {tasks['total']} total")


# ─── Claude interaction ───────────────────────────────────────────────────────


def get_git_head() -> str:
    """Return the current HEAD commit hash (short)."""
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        capture_output=True, text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def get_git_branch() -> str:
    """Return the current branch name."""
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        capture_output=True, text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def get_commits_since(ref: str) -> list[dict]:
    """Return commits made since the given ref."""
    result = subprocess.run(
        ["git", "log", f"{ref}..HEAD", "--oneline", "--no-decorate"],
        capture_output=True, text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return []

    commits = []
    for line in result.stdout.strip().splitlines():
        parts = line.split(" ", 1)
        if len(parts) == 2:
            commits.append({"hash": parts[0], "message": parts[1]})
    return commits


def get_diff_stat_since(ref: str) -> str:
    """Return a short diffstat since the given ref."""
    result = subprocess.run(
        ["git", "diff", "--stat", f"{ref}..HEAD"],
        capture_output=True, text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def run_claude_iteration(prompt_file: str) -> dict:
    """Run a single Claude CLI iteration and parse the streaming JSON output.

    Returns dict with: success, tokens_in, tokens_out, duration_s, error.
    """
    prompt_text = Path(prompt_file).read_text()

    start = time.monotonic()
    result_data = {
        "success": False,
        "tokens_in": 0,
        "tokens_out": 0,
        "cache_read": 0,
        "cache_creation": 0,
        "duration_s": 0,
        "cost_usd": 0,
        "error": None,
    }

    try:
        proc = subprocess.Popen(
            [
                "claude", "-p",
                "--dangerously-skip-permissions",
                "--output-format", "stream-json",
                "--model", "opus",
                "--verbose",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        stdout, stderr = proc.communicate(input=prompt_text)
        result_data["duration_s"] = time.monotonic() - start

        # Parse streaming JSON — each line is a JSON object
        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            etype = event.get("type", "")

            # Collect usage from the result event
            if etype == "result":
                result_data["cost_usd"] = event.get("total_cost_usd", 0)
                result_data["success"] = True

                # modelUsage has cumulative per-model totals
                model_usage = event.get("modelUsage", {})
                tokens_in = 0
                tokens_out = 0
                cache_read = 0
                cache_creation = 0
                for model_stats in model_usage.values():
                    tokens_in += model_stats.get("inputTokens", 0)
                    tokens_out += model_stats.get("outputTokens", 0)
                    cache_read += model_stats.get("cacheReadInputTokens", 0)
                    cache_creation += model_stats.get("cacheCreationInputTokens", 0)
                result_data["tokens_in"] = tokens_in
                result_data["tokens_out"] = tokens_out
                result_data["cache_read"] = cache_read
                result_data["cache_creation"] = cache_creation

        if proc.returncode != 0 and not result_data["success"]:
            result_data["error"] = stderr.strip() or f"Claude exited with code {proc.returncode}"

    except FileNotFoundError:
        result_data["error"] = "Claude CLI not found. Is it installed and on PATH?"
    except Exception as e:
        result_data["error"] = str(e)

    return result_data


# ─── Token formatting ────────────────────────────────────────────────────────


def fmt_tokens(n: int) -> str:
    """Format token count in a human-readable way."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


def fmt_duration(seconds: float) -> str:
    """Format seconds into human-readable duration."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    if minutes < 60:
        return f"{minutes}m {secs}s"
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}h {mins}m"


def fmt_cost(usd: float) -> str:
    """Format USD cost."""
    if usd < 0.01:
        return f"${usd:.4f}"
    return f"${usd:.2f}"


# Using opus context window size (200k)
CONTEXT_WINDOW = 200_000


def print_iteration_report(
    iteration: int,
    iter_result: dict,
    totals: dict,
    head_before: str,
) -> None:
    """Print a human-readable report after a loop iteration."""

    section(f"Iteration {iteration} Complete")

    # Duration
    info(f"Duration: {fmt_duration(iter_result['duration_s'])}")

    # Token usage for this iteration
    ctx_tokens = iter_result["tokens_in"]
    ctx_pct = (ctx_tokens / CONTEXT_WINDOW) * 100 if CONTEXT_WINDOW > 0 else 0
    print()
    info(f"This iteration:")
    print(f"      Input:  {c(CYAN, fmt_tokens(iter_result['tokens_in']))} tokens")
    print(f"      Output: {c(CYAN, fmt_tokens(iter_result['tokens_out']))} tokens")
    if iter_result["cache_read"]:
        print(f"      Cache read: {c(DIM, fmt_tokens(iter_result['cache_read']))} tokens")
    print(f"      Context: {c(YELLOW, f'{ctx_pct:.1f}%')} of {fmt_tokens(CONTEXT_WINDOW)} window")
    if iter_result["cost_usd"]:
        print(f"      Cost: {c(DIM, fmt_cost(iter_result['cost_usd']))}")

    # Running totals
    print()
    info(f"Running totals ({iteration} iteration{'s' if iteration != 1 else ''}):")
    print(f"      Input:  {c(CYAN, fmt_tokens(totals['tokens_in']))} tokens")
    print(f"      Output: {c(CYAN, fmt_tokens(totals['tokens_out']))} tokens")
    print(f"      Cost:   {c(DIM, fmt_cost(totals['cost_usd']))}")
    print(f"      Time:   {fmt_duration(totals['duration_s'])}")

    # Changes summary
    commits = get_commits_since(head_before)
    if commits:
        print()
        info(f"Commits this iteration:")
        for cm in commits:
            print(f"      {c(YELLOW, cm['hash'])} {cm['message']}")

        diffstat = get_diff_stat_since(head_before)
        if diffstat:
            last_line = diffstat.splitlines()[-1] if diffstat else ""
            if last_line:
                print(f"      {c(DIM, last_line.strip())}")
    else:
        print()
        info(f"No new commits this iteration")

    print()


# ─── Prompt generation ─────────────────────────────────────────────────────────


def init_project() -> int:
    """Generate prompt files and update .gitignore for loop usage."""
    # Generate prompt files
    files = {
        BUILD_PROMPT: BUILD_PROMPT_TEMPLATE,
        PLAN_PROMPT: PLAN_PROMPT_TEMPLATE,
    }

    for filename, content in files.items():
        path = Path(filename)
        if path.exists():
            warn(f"{filename} already exists, overwriting")
        path.write_text(content)
        success(f"Generated {filename}")

    # Update .gitignore
    gitignore_entries = [PLAN_PROMPT, BUILD_PROMPT, IMPLEMENTATION_PLAN]
    gitignore_path = Path(".gitignore")

    existing_lines = set()
    if gitignore_path.exists():
        existing_lines = set(gitignore_path.read_text().splitlines())

    to_add = [entry for entry in gitignore_entries if entry not in existing_lines]

    if to_add:
        with open(gitignore_path, "a") as f:
            # Add a newline before our entries if file exists and doesn't end with one
            if gitignore_path.stat().st_size > 0:
                existing = gitignore_path.read_text()
                if not existing.endswith("\n"):
                    f.write("\n")
            for entry in to_add:
                f.write(f"{entry}\n")
        success(f"Added {', '.join(to_add)} to .gitignore")
    else:
        info("All entries already in .gitignore")

    print()
    info("Next steps:")
    info(f"  1. Review and customise the generated prompts")
    info(f"  2. Create specs/ directory with your application specifications")
    info(f"  3. Run: python loop.py plan")
    print()

    return 0


# ─── Main loop ────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="loop.py",
        description="Ralph Wiggum Loop — drive Claude Code iteratively.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            examples:
              %(prog)s init               Generate prompts and update .gitignore
              %(prog)s build              Build mode, runs until plan is complete
              %(prog)s build -n 10        Build mode, max 10 iterations
              %(prog)s build --no-stop    Build mode, don't stop when plan is complete
              %(prog)s plan               Plan mode, 20 iterations (default)
              %(prog)s plan -n 5          Plan mode, 5 iterations
        """),
    )

    subparsers = parser.add_subparsers(dest="mode", help="Operating mode")

    # Build mode
    build_parser = subparsers.add_parser("build", help="Implement from IMPLEMENTATION_PLAN.md")
    build_parser.add_argument(
        "-n", "--max-iterations", type=int, default=BUILD_DEFAULT_ITERATIONS,
        help="Max iterations (0 = unlimited, default: unlimited)",
    )
    build_parser.add_argument(
        "--no-stop", action="store_true",
        help="Don't stop when all plan tasks are complete",
    )

    # Plan mode
    plan_parser = subparsers.add_parser("plan", help="Generate/update IMPLEMENTATION_PLAN.md")
    plan_parser.add_argument(
        "-n", "--max-iterations", type=int, default=PLAN_DEFAULT_ITERATIONS,
        help=f"Max iterations (default: {PLAN_DEFAULT_ITERATIONS})",
    )

    # Init mode
    subparsers.add_parser(
        "init",
        help="Generate prompt files and update .gitignore",
    )

    args = parser.parse_args()

    if args.mode is None:
        parser.print_help()
        return 1

    # Handle init early — it doesn't need the loop infrastructure
    if args.mode == "init":
        return init_project()

    mode = args.mode
    max_iterations = args.max_iterations
    stop_on_complete = mode == "build" and not getattr(args, "no_stop", False)

    prompt_file = PLAN_PROMPT if mode == "plan" else BUILD_PROMPT

    # ── Precondition checks ──────────────────────────────────────────────

    banner(f"Ralph Wiggum Loop — {mode.upper()} mode")

    section("Preflight Checks")

    # 1. Git repo
    if not check_git_repo():
        error("Not inside a git repository.")
        info("Run this from within a git project directory.")
        return 1
    success("Git repository detected")

    # 2. Clean worktree
    if not check_clean_worktree():
        print()
        error("Working tree is not clean.")
        info("Commit or stash your changes before starting the loop.")
        return 1
    success("Working tree is clean")

    # 3. Auto-compact
    if not check_auto_compact():
        return 1
    success("Auto-compact is not enabled")

    # 4. Auto-memory
    if not check_auto_memory():
        return 1
    success("Auto-memory is not enabled")

    # 5. Prompt file
    if not check_prompt_file(prompt_file):
        return 1
    success(f"Prompt file found: {prompt_file}")

    # ── Show initial state ───────────────────────────────────────────────

    branch = get_git_branch()
    head = get_git_head()

    section("Configuration")
    info(f"Mode:       {c(BOLD, mode.upper())}")
    info(f"Branch:     {c(CYAN, branch)}")
    info(f"Head:       {c(DIM, head)}")
    info(f"Prompt:     {prompt_file}")
    if max_iterations > 0:
        info(f"Max iters:  {max_iterations}")
    else:
        info(f"Max iters:  {c(DIM, 'unlimited')}")
    if mode == "build":
        info(f"Stop on completion: {c(GREEN, 'yes') if stop_on_complete else c(DIM, 'no')}")

    # Show plan status if in build mode
    if mode == "build":
        plan_tasks = parse_plan_tasks()
        if plan_tasks["total"] > 0:
            section("Implementation Plan")
            print_plan_summary(plan_tasks)
        else:
            print()
            warn("No IMPLEMENTATION_PLAN.md found or no tasks in it.")
            info("Consider running in plan mode first.")

    # ── Run loop ─────────────────────────────────────────────────────────

    totals = {
        "tokens_in": 0,
        "tokens_out": 0,
        "cost_usd": 0,
        "duration_s": 0,
    }

    start_time = time.monotonic()
    iteration = 0

    try:
        while True:
            iteration += 1

            # Check iteration limit
            if max_iterations > 0 and iteration > max_iterations:
                print()
                success(f"Reached max iterations ({max_iterations}). Stopping.")
                break

            # In build mode, check if plan is complete
            if stop_on_complete and iteration > 1:
                plan_tasks = parse_plan_tasks()
                if plan_tasks["total"] > 0 and plan_tasks["pending"] == 0:
                    print()
                    banner("All tasks complete!")
                    print_plan_summary(plan_tasks)
                    success("Implementation plan is fully checked off. Stopping.")
                    break

            # ── Iteration header ─────────────────────────────────────────

            iter_label = f"Iteration {iteration}"
            if max_iterations > 0:
                iter_label += f" / {max_iterations}"

            print()
            print(c(CYAN, f"  {'─' * 50}"))
            print(c(BOLD, f"  {iter_label}  ({mode.upper()})"))
            print(c(CYAN, f"  {'─' * 50}"))

            if mode == "build":
                plan_tasks = parse_plan_tasks()
                if plan_tasks["total"] > 0:
                    print_plan_summary(plan_tasks)

            head_before = get_git_head()

            # ── Run Claude ───────────────────────────────────────────────

            info("Running Claude...")
            print()

            iter_result = run_claude_iteration(prompt_file)

            if not iter_result["success"]:
                error(f"Claude iteration failed: {iter_result.get('error', 'unknown error')}")
                if iteration == 1:
                    return 1
                warn("Continuing to next iteration...")
                continue

            # Update totals
            totals["tokens_in"] += iter_result["tokens_in"]
            totals["tokens_out"] += iter_result["tokens_out"]
            totals["cost_usd"] += iter_result["cost_usd"]
            totals["duration_s"] += iter_result["duration_s"]

            # ── Post-iteration report ────────────────────────────────────

            print_iteration_report(iteration, iter_result, totals, head_before)


    except KeyboardInterrupt:
        print()
        print()
        warn("Interrupted by user.")

    # ── Final summary ────────────────────────────────────────────────────

    wall_time = time.monotonic() - start_time

    banner("Loop Complete")

    info(f"Iterations completed: {c(BOLD, str(iteration - 1))}")
    info(f"Wall time: {fmt_duration(wall_time)}")

    section("Total Token Usage")
    print(f"      Input:  {c(CYAN, fmt_tokens(totals['tokens_in']))}")
    print(f"      Output: {c(CYAN, fmt_tokens(totals['tokens_out']))}")
    if totals["cost_usd"]:
        print(f"      Cost:   {c(DIM, fmt_cost(totals['cost_usd']))}")

    if mode == "build":
        plan_tasks = parse_plan_tasks()
        if plan_tasks["total"] > 0:
            section("Final Plan Status")
            print_plan_summary(plan_tasks)

    head_final = get_git_head()
    info(f"HEAD: {c(DIM, head_final)}")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
