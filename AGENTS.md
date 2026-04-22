# AGENTS.md

Follow `CORE.md` first; this file only adds Codex-specific operational notes.
System and Codex runtime instructions still take precedence over repository
docs.

## Codex Notes

- Shared project commands, migrations, invariants, and validation expectations
  live in `CORE.md`.
- Keep edits scoped to the requested files or the smallest needed module set.
- Preserve unrelated uncommitted work in this repository.
- When prior decisions, fixes, or session history are relevant, use claude-mem
  in this order: `search`, then `timeline`, then `get_observations` for only the
  filtered IDs needed.

## Project Pointers

- Workout strings and `weekly_baseline` are hard project invariants owned by
  `CORE.md`.
- Dynamic memory summaries belong in generated context, not in committed
  instruction files.


<claude-mem-context>
# Memory Context

# [Temperance] recent context, 2026-04-21 10:58pm GMT-3

Legend: 🎯session 🔴bugfix 🟣feature 🔄refactor ✅change 🔵discovery ⚖️decision
Format: ID TIME TYPE TITLE
Fetch details: get_observations([IDs]) | Search: mem-search skill

Stats: 10 obs (3,321t read) | 104,156t work | 97% savings

### Apr 21, 2026
17 12:24a 🔵 Documentation Overlap Identified in agents.md, core.md, and claude.md
26 9:58a 🔵 claude-mem shared Claude+Codex memory setup: CLAUDE_MEM_PROVIDER as offload point
27 " 🔵 claude-mem CLAUDE_MEM_PROVIDER investigation initiated
28 9:59a 🔵 claude-mem CLAUDE_MEM_PROVIDER supports claude/gemini/openrouter — not codex
29 " 🔵 Claude-Mem Shared Memory Setup Issue: Heavy Processing Offload to Codex via CLAUDE_MEM_PROVIDER
30 10:00a 🔵 claude-mem shared memory setup investigation: heavy processing and CLAUDE_MEM_PROVIDER
31 " 🔵 claude-mem shared memory setup: CLAUDE_MEM_PROVIDER as Codex routing key
32 10:01a 🔵 claude-mem CLAUDE_MEM_PROVIDER config identified as Codex routing point
33 " 🔵 claude-mem failure root cause: Claude API usage limit hit at ~11:28pm on 2026-04-20
34 10:05a 🔵 claude-mem shared Claude+Codex memory setup investigation
S23 Implemented OAuth2 with PKCE flow in authentication system. (Apr 21 at 6:01 PM)
S24 [Session Startup Hook Error Resolution] (Apr 21 at 6:08 PM)
S25 Added secure user login using modern protocols for enhanced security. (Apr 21 at 6:18 PM)
S26 [Regressed Button Functionality] (Apr 21 at 6:24 PM)
S27 "Feature: Enhanced card title functionality" (Apr 21 at 8:30 PM)
S28 [Check Vite Server Status] (Apr 21 at 8:32 PM)
S29 [Adjusting Button Appearance] (Apr 21 at 9:12 PM)
S30 [Type Checking] (Apr 21 at 9:43 PM)
S31 [Adjust Button Sizes for Better UI Consistency and Accessibility] (Apr 21 at 9:52 PM)
S32 Browser Zoom Reset Functionality Added to GStack Skill (Apr 21 at 10:47 PM)
**Learned**: [The 'gstack' skill now includes functionality for adjusting the web page viewport size via JavaScript commands.]

**Completed**: Browser Zoom Reset Functionality Added to GStack Skill — A new feature was implemented allowing users to reset the browser's zoom level using a specific command.


Access 104k tokens of past work via get_observations([IDs]) or mem-search skill.
</claude-mem-context>