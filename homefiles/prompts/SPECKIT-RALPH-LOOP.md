# Spec Kit + Ralph Wiggum Autonomous Loop

You are running inside an autonomous loop. Each iteration, you receive this
prompt and must make progress toward completing all tasks.

## Instructions

1. Read `.speckit/tasks.md` to get the current task list.
2. Count incomplete tasks (lines without `[x]`).
3. If zero incomplete tasks remain, output `<promise>ALL_TASKS_DONE</promise>` and stop.
4. Pick the **first** incomplete task and execute `/speckit.implement` for it.
5. Run tests to validate your implementation. Tests must pass before continuing.
6. Mark the completed task with `[x]` in `.speckit/tasks.md`.
7. Commit your changes with a descriptive message.

## Rules

- **One task per iteration.** Do not attempt multiple tasks in a single pass.
- **Tests must pass** before marking a task complete.
- **Follow the constitution.** Respect all principles defined in `.speckit/constitution.md`.
- **Do not skip tasks.** Work through them in order.
- **Do not terminate early.** Only output the completion promise when all tasks are done.

## Context

The LLM is stateless but the filesystem is not. Each iteration you will see
the accumulated state from previous iterations through file changes. Use
`.speckit/tasks.md` as your source of truth for progress.
