# CORE.md

Shared guidelines for all AI agents working in this repository.

## Working style

- Start every task by restating the goal, key constraints, and acceptance criteria concisely.
- If requirements are unclear, ask 1-3 focused clarifying questions before making risky changes.
- For non-trivial tasks, propose a brief plan (2-6 bullets) before executing. Wait for confirmation when the plan includes risky or high-churn changes; otherwise name the assumption and keep moving.
- Prefer small, reviewable diffs over full-file rewrites unless explicitly requested.
- After behavior-changing edits, summarize what changed and how to verify it.

## Editing code

- Make the smallest safe change that solves the problem.
- Avoid code duplication; reuse existing code wherever possible.
- Preserve the existing code style and conventions.
- When you touch a function or module, ensure types, imports, and error handling remain consistent.
- Do not silently rename, move, or create files that change project structure without stating that intent first.

## Tests and validation

- Whenever you change behavior, add or update tests when practical. If you do not add tests, explain what should be validated.
- Call out important assumptions, follow-ups, or residual risks in the final handoff.

## Temperance v2 specific

- After any backend change that needs a restart, run `./temperance/scripts/install_keepalive.sh restart`.
