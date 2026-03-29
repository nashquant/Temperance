# AGENTS.md

## Working style
- Start every task by restating the goal, key constraints, and acceptance criteria in your own words. Keep it brief and concrete.
- If the user references a file, prompt, or artifact, check whether it exists before editing. If it does not exist, say so explicitly and state whether you will create it.
- If requirements are unclear, ask 1-3 focused clarifying questions before making risky changes.
- If the user provides a skill or inline instruction block, treat it as active task guidance and say which workflow you are following.
- For non-trivial tasks, propose a brief plan (2-6 bullets) before executing. Wait for confirmation when the plan includes risky or high-churn changes; otherwise name the assumption and keep moving.
- Prefer small, reviewable diffs instead of full-file rewrites unless explicitly requested.

## Editing Code
- Preserve the existing code style and conventions in this project.
- Make the smallest safe change that solves the problem.
- Avoid code duplication; whenever possible, reuse code from another part of the codebase.
- When you touch a function or module, ensure types, imports, and error handling remain consistent.
- Do not silently rename, move, or create files that change project structure without stating that intent first.

## Tests and validation
- Whenever you change behavior, add or update tests when practical. If you do not add tests, explain what should be validated.
- At the end of a task, summarize what changed, why it changed, and how to verify it with commands or manual steps.
- Call out important assumptions, follow-ups, or residual risks in the final handoff.
