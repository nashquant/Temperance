---
type: index
status: active
created: 2026-04-20
updated: 2026-04-24
tags:
  - wiki
sources: []
---

# Wiki Index

Read this file first when working with the wiki. Keep entries short: link, type, one-line summary.

Prefix convention: `_` meta · `src-` source summary · `proj-` project · `ref-` reference · no prefix = topic/concept.

## Meta

- [[_home]] | _ | Entry point and orientation for the Agents vault wiki.
- [[_intake]] | _ | Rules for storing raw sources and turning them into wiki pages.
- [[_source-library]] | _ | Description of `Agents/raw/` folder structure.
- [[_questions]] | _ | Parking lot for unresolved questions and future investigations.
- [[_template-source]] | _ | Template for source summary pages.
- [[_template-topic]] | _ | Template for topic/concept pages.

## Source Summaries

- [[src-claude-agents-config]] | src | Claude-side context discipline, bounded search/read rules, claude-mem handoff behavior.
- [[src-claude-mem-dev-instructions]] | src | claude-mem architecture: hooks, worker, SQLite, Chroma, skills, privacy tags, build commands, exit codes.
- [[src-codex-agents-config]] | src | Codex runtime guardrails, token-budget discipline, and claude-mem operating boundaries.
- [[src-claude-mem-observations-2026-04-21]] | src | Memory observations about claude-mem provider routing, failure modes, and Ollama shim setup.
- [[src-iterm2-hotkey-2026-04-23]] | src | Setup code, verification output, and backup paths for the Vibe Coding iTerm2 hotkey workspace.
- [[src-ollama-library-model-families-2026-04-24]] | src | Bounded official Ollama library snapshot for helper-model, coder-model, and embedding-model examples.

## Projects

- [[proj-spg-maestro]] | proj | SPG Maestro project home note migrated from the legacy vault.
- [[proj-reprocess-phi3-observations]] | proj | Plan to replace 94 phi3 observations by resetting JSONL offsets and re-ingesting with qwen2.5:1.5b.

## References

- [[ref-huggingface]] | ref | Hugging Face platform overview: models, datasets, Spaces, key libraries (transformers/diffusers/peft/trl), and learning resources.

## Topics

- [[Agentic Harness]] | topic | Meta mental model: six harness layers, best practices, limitations, criticisms, and how the pattern is expected to evolve.
- [[Agent Booting Protocol]] | topic | Orientation gap diagnosis, five boot phases, current state audit (Claude Code vs Codex), and concrete gaps to fix.
- [[Bootstrap Models Mental Model]] | topic | Role model for primary vs helper models, Ollama-grounded examples, trust boundaries, and support-layer heuristics.
- [[Booting Protocol Best Practices]] | topic | General best practices: five phases, three mechanisms, restricted-environment strategy, and the minimal viable boot protocol.
- [[Agent Prompt Notifications]] | topic | iTerm-independent prompt notification watcher, LaunchAgent files, memory footprint, and zsh tradeoffs.
- [[Agent Workspace Operating System]] | topic | Layer map for terminal setup, runtime instructions, claude-mem, observability, and vault documentation.
- [[Claude-mem Access Workflow]] | topic | How Codex should search, contextualize, and fetch memory from claude-mem.
- [[Claude-mem in My Setup]] | topic | Current-state map of claude-mem ownership, layers, and where the local setup is principled versus ad hoc.
- [[Claude-mem Processing Architecture]] | topic | Current shared-memory architecture, provider lesson, failure modes, and Codex extractor implications.
- [[Context Window Management Mental Model]] | topic | Working-set mental model for context pressure, failure modes, staged retrieval, and thin-boot discipline.
- [[Codex Terminal Token Status Bar]] | topic | zsh right-prompt status for Codex context-window and rate-limit usage.
- [[Hooks Mental Model]] | topic | Lifecycle mental model for automatic runtime trigger points, plus how hook ownership maps onto your current setup.
- [[iTerm2 Agentic Setup]] | topic | Operating contract for the two-pane iTerm2 workspace using the Vibe Coding profile.
- [[MCP Mental Model]] | topic | Generic MCP framework mental model with a mapped view of your current Claude/Codex setup.
- [[Memory Systems Mental Model]] | topic | General mental model for capture, extraction, storage, retrieval, and reuse, with claude-mem as the running example.
- [[Observation Generation Pipeline]] | topic | How claude-mem generates observations: prompts.ts, Ollama shim internals, GeminiAgent, OpenRouterAgent.
- [[Ollama Issues in Claude-mem]] | topic | Model quality comparison, quarantine mechanics, phi3→qwen2.5 reprocessing (completed 2026-04-23).
- [[Plugins Mental Model]] | topic | Packaging mental model for skills, MCP servers, apps, and extension ownership in agent runtimes.
- [[gstack Skills]] | topic | Synced active skill set for Claude Code + Codex, disabled/deleted rationale, and re-enable guide.
- [[Superpowers Skills]] | topic | Mental model for the superpowers discipline layer: pre-work gates, execution skills, and completion gates.
- [[OMX - Oh My Codex]] | topic | Runtime enhancement layer for Codex CLI: clarify→plan→execute spine, 4 core skills, .omx/ state, and team parallelism.
