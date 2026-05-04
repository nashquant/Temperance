---
type: log
status: active
created: 2026-04-20
updated: 2026-04-24
tags:
  - wiki
sources: []
---

# Wiki Log

Append entries only. Use consistent headings so the log is easy to scan and parse.

## [2026-04-20] restructure | LLM wiki scaffold

- Created the `40 Wiki/` generated knowledge layer.
- Created the `50 Sources/` immutable raw source layer.
- Added [[Source Library]] as the raw source entry note.
- Added root `AGENTS.md` with ingest, query, lint, indexing, and logging rules.
- Preserved `00 Inbox/Scratchpad.md` as the fast-capture scratchpad.

## [2026-04-21] maintenance | Codex operating guidance persisted

- Updated root `AGENTS.md` with compact Codex token-budget guardrails.
- Persisted claude-mem operational boundaries and health-check references for future sessions.

## [2026-04-21] ingest | Codex agents configuration

- Corrected root `AGENTS.md` back to vault operating policy instead of duplicating the external Codex setup source.
- Ingested `50 Sources/Articles/CODEX AGENTS.MD` into [[Codex Agents Configuration]].
- Added [[Claude-mem Access Workflow]] as the durable wiki topic for memory access.
- Updated [[index]] with the new source summary and topic page.

## [2026-04-21] maintenance | Claude-mem reference compression

- Compressed [[MEMORY]] into a concise operational reference.
- Added a short root `AGENTS.md` pointer to the reference instead of duplicating claude-mem setup details.
- Updated [[index]] to include the non-wiki reference note.

## [2026-04-21] maintenance | MEMORY reference rename

- Renamed `Codex Powered Claude-mem.md` to [[MEMORY]].
- Updated root `AGENTS.md` and [[index]] to point at the new name.

## [2026-04-21] memory-ingest | Claude-mem operating knowledge

- Queried `claude-mem` with the search -> timeline -> `get_observations` workflow.
- Added [[Claude-mem Memory Observations 2026-04-21]] as a traceable summary of selected memory observations.
- Added [[Claude-mem Processing Architecture]] to preserve the provider correction, failure mode, current Ollama shim model, and future extractor implication.
- Updated [[Claude-mem Access Workflow]] and [[index]] with the new links.

## [2026-04-23] migration | Multi-vault split

- Migrated agent, Codex, and claude-mem wiki pages from the legacy `Second Brain` vault into `Agents/wiki/`.
- Migrated Codex, Claude, and claude-mem raw source captures into `Agents/raw/Articles/`.
- Migrated [[SPG Maestro]] into `Agents/wiki/Projects/`.
- Updated current source-intake guidance from the old `40 Wiki/` and `50 Sources/` paths to the new `wiki/` and `raw/` vault contract.

## [2026-04-23] capture | iTerm2 Vibe Coding hotkey setup

- Captured the iTerm2 setup code in `raw/Articles/iTerm2 Vibe Coding Hotkey Setup 2026-04-23.md`.
- Added [[iTerm2 Vibe Coding Hotkey Setup 2026-04-23]] as the source summary for the implementation.
- Added [[iTerm2 Agentic Setup]] as the operational topic note under Agents.
- Updated [[index]] with the new source and topic links.

## [2026-04-23] bugfix | iTerm2 launch crash after hotkey setup

- Diagnosed iTerm2 crash reports showing `-[__NSCFBoolean isEqualToString:]` during session launch.
- Fixed the `Vibe Coding` profile by restoring `Custom Directory` from boolean `True` to string `'No'`.
- Verified a clean iTerm2 relaunch and live hotkey read-back of `Vibe Coding:2`.
- Updated [[iTerm2 Vibe Coding Hotkey Setup 2026-04-23]] and [[iTerm2 Agentic Setup]] with the type invariant.

## [2026-04-23] enhancement | iTerm2 hotkey keeper

- Added a user LaunchAgent, `com.matheus.iterm2-vibe-hotkey-keeper`, so iTerm2 stays available for the app-owned hotkey.
- Added `/Users/matheus/Library/Application Support/iTerm2/keep-vibe-hotkey-alive.sh` to relaunch iTerm hidden and run the AutoLaunch script when iTerm is absent.
- Verified the close/relaunch path: after quitting iTerm, launchd restarted it and live read-back returned `Vibe Coding:2`.
- Updated [[iTerm2 Vibe Coding Hotkey Setup 2026-04-23]] and [[iTerm2 Agentic Setup]] with the keeper contract.

## [2026-04-23] bugfix | iTerm2 keeper raw-window launch

- Removed the keeper's direct `open -a iTerm` launch path and made it launch through the compiled AutoLaunch script.
- Set `OpenNoWindowsAtStartup = true` for iTerm2 so app startup does not create a raw normal window before the hotkey profile is prepared.
- Verified close/relaunch read-back: `windows=1`, with the single window `hotkey=true,profile=Vibe Coding,sessions=2`.
- Updated [[iTerm2 Vibe Coding Hotkey Setup 2026-04-23]] and [[iTerm2 Agentic Setup]] with the startup preference.

## [2026-04-23] tuning | iTerm2 font and agent prompt alerts

- Increased the `Vibe Coding` profile font from `Monaco 12` to `Monaco 13`.
- Enabled bell attention behavior with Growl/user notifications, visual bell, and flashing bell while keeping bell unsilenced.
- Added instant iTerm prompt triggers for common approval, user-input, yes/no, and continue prompts, with notification and Dock-bounce actions.
- Verified profile read-back, LaunchAgent state, and live window state `windows=1`, `profile=Vibe Coding`, `sessions=2`.

## [2026-04-23] tuning | iTerm2 font 14 and Cmd-backtick hotkey

- Increased the `Vibe Coding` profile font from `Monaco 13` to `Monaco 14`.
- Switched the sole iTerm2 global hotkey from `Cmd+\` to ``Cmd+` `` with key code `50` and command modifier flags `1048576`.
- Verified profile read-back and live window state `windows=1`, `profile=Vibe Coding`, `sessions=2`.
- Updated [[iTerm2 Vibe Coding Hotkey Setup 2026-04-23]] and [[iTerm2 Agentic Setup]] with the new font and hotkey.

## [2026-04-23] bugfix | iTerm2 Cmd+C menu crash

- Diagnosed fresh crash reports showing `NSMenuItem initWithTitle:action:keyEquivalent:` under `iTermApplicationDelegate menuNeedsUpdate` after Cmd+C.
- Cleared `Vibe Coding` profile `Shortcut = 'C'`, which conflicted with Cmd+C menu/key-equivalent handling.
- Restarted iTerm2 through the keeper and verified the profile shortcut is empty with no newer crash report during the follow-up checks.
- Updated [[iTerm2 Vibe Coding Hotkey Setup 2026-04-23]] and [[iTerm2 Agentic Setup]] with the shortcut invariant.

## [2026-04-23] rollback | iTerm2 trigger notifications and Cmd-backtick

- Crashes continued after clearing `Shortcut = 'C'`; newest reports still showed `NSMenuItem initWithTitle:action:keyEquivalent:` under `iTermApplicationDelegate menuNeedsUpdate`.
- Rolled the global hotkey back to `Cmd+\` and removed all `Vibe Coding` trigger entries.
- Kept `Monaco 14`, the hotkey keeper, `OpenNoWindowsAtStartup`, and the two-pane AutoLaunch script.
- Verified stable read-back after restart: `Shortcut=''`, `HotKey='\\' 42`, `Triggers=[]`, `windows=1`, `profile=Vibe Coding`, `sessions=2`, with no newer crash report during verification.

## [2026-04-23] checkpoint | Cmd-backtick without triggers

- Re-applied only the `Cmd+`` hotkey while leaving `Vibe Coding` `Triggers=[]` and `Shortcut=''`.
- Verified profile read-back: hotkey character `` ` ``, key code `50`, command modifier flags `1048576`, `Monaco 14`, and no trigger entries.
- Restarted iTerm2 through the keeper and verified `windows=1`, `profile=Vibe Coding`, `sessions=2`.
- No newer iTerm2 crash report appeared during this checkpoint.

## [2026-04-23] capture | Codex terminal token status bar

- Added [[Codex Terminal Token Status Bar]] as the operational topic note for the zsh right-prompt usage bar.
- Captured the parser path, shell hook, display format, verification commands, and caveats.
- Updated [[index]] with the new topic link.

## [2026-04-23] fix | Token status display scope

- Fixed zsh prompt escaping by replacing literal `%` with `%%` before assigning `RPROMPT`.
- Gated the zsh prompt display behind `CODEX_TOKEN_STATUS_PROMPT` so ordinary terminal prompts stay clean.
- Updated Claude Code `statusLine.command` to print the token status at the bottom while preserving OnWatch status-line input capture.
- Updated [[Codex Terminal Token Status Bar]] with the Claude status-line path and Codex TUI limitation.

## [2026-04-23] rollback | Remove zsh token prompt

- Removed the zsh `precmd`/`RPROMPT` token status hook because plain shell prompts are not useful during Codex or Claude TUI sessions.
- Kept the `codex-token-status` shell helper and Claude Code native bottom `statusLine.command`.
- Updated [[Codex Terminal Token Status Bar]] to describe the current supported surfaces.

## [2026-04-23] implementation | Codex app-server usage sidecar

- Added `/Users/matheus/.codex/scripts/codex-usage-sidecar.py` to initialize `codex app-server --listen stdio://`, listen for token and rate-limit usage notifications, and write `/tmp/codex-usage-status.json`.
- Updated `/Users/matheus/.codex/scripts/codex-token-status.py` to prefer fresh sidecar state and fall back to session JSONL parsing.
- Extended `/Users/matheus/.codex/scripts/test_codex_token_status.py` to cover both JSONL and app-server state formatting.
- Updated [[Codex Terminal Token Status Bar]] with the sidecar route and the stock TUI fallback boundary.

## [2026-04-23] implementation | Codex visible token title wrapper

- Added `/Users/matheus/.codex/scripts/codex-with-token-title` as an external renderer for Codex TUI sessions.
- Added `.zshrc` helper `codex-with-token-title`, which launches Codex and updates the terminal title plus iTerm2 badge with `codex-token-status.py --no-color`.
- Documented that this is not a native in-TUI bottom bar; it is the visible iTerm2 chrome workaround while Codex lacks a status-line hook.

## [2026-04-23] capture | Agent prompt notifications

- Added [[Agent Prompt Notifications]] as the operational topic note for iTerm-independent prompt notifications.
- Captured the LaunchAgent, watcher, config, state, log paths, iTerm trigger boundary, measured memory footprint, zsh alternative tradeoffs, and rollback command.
- Updated [[index]] with the new topic link.

## [2026-04-23] maintenance | Agents wiki organization pass

- Added [[Claude Agents Configuration]] and [[Claude-mem Development Instructions]] for raw source captures that were not yet represented in `wiki/Sources/`.
- Added [[Agent Workspace Operating System]] as the synthesis hub connecting terminal setup, runtime instruction bridges, claude-mem, prompt/status observability, and vault documentation.
- Cleaned [[Wiki Home]] and [[Source Library]] so they match the current `Agents/` vault contract instead of legacy second-brain links.
- Cleaned [[SPG Maestro]] as a placeholder project note and removed links to legacy pages absent from this vault.
- Updated [[index]] with the new source summaries and synthesis page.

## [2026-04-24] maintenance | Temperance concept reframing

- Added [[Temperance Product Mental Model]] to explain Temperance as a local-first training control system rather than an implementation stack.
- Added [[Temperance Metrics and How To Use Them]] to explain the main metrics in plain language, with interaction guidance and explicit concept gaps.
- Updated [[_index]] so both Temperance concept notes are part of the durable wiki navigation.

## [2026-04-24] correction | Temperance topics moved out of Agents

- Removed the misplaced Temperance concept pages from `Agents/wiki/` because they belong in the dedicated `Temperance` vault.
- Kept `Agents` scoped to agentic framework, workflow, memory, and prompt/process architecture topics.

## [2026-04-24] synthesis | Agent framework mental models

- Added [[MCP Mental Model]] as a layered explanation of client, protocol, server, tools, resources, and current setup mapping.
- Added [[Hooks Mental Model]] to distinguish automatic runtime lifecycle behavior from explicit tool use.
- Added [[Plugins Mental Model]] to separate packaging boundaries from the concrete capabilities shipped inside them.
- Updated [[_index]] so the new mental-model pages are part of the durable Agents navigation.

## [2026-04-24] synthesis | Memory systems and claude-mem setup map

- Added [[Memory Systems Mental Model]] as the generic framework page for capture, extraction, storage, retrieval, and reuse, using claude-mem as the running example.
- Added [[Claude-mem in My Setup]] as the current-state bridge between the general memory concept and the local Claude/Codex/worker/MCP/vault arrangement.
- Linked both pages with the existing claude-mem workflow and architecture notes, and updated [[_index]] so the new mental-model pages are part of durable navigation.

## [2026-04-24] synthesis | Context windows and bootstrap models

- Added [[Context Window Management Mental Model]] as the working-set note for context pressure, compression, staged retrieval, and thin-boot operator practice.
- Added [[Bootstrap Models Mental Model]] to separate primary reasoning models from helper/support models, embeddings, retrieval, and human-curated documentation.
- Added [[src-ollama-library-model-families-2026-04-24]] as a bounded source summary grounded in the official Ollama library plus supporting Hugging Face references.
- Updated [[_index]] so the new topic pages and source summary are part of durable Agents-vault navigation.
