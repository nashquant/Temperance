---
type: topic
status: active
created: 2026-04-24
updated: 2026-04-24
tags:
  - wiki
  - agents
  - context
  - operations
sources:
  - "[[src-claude-agents-config]]"
  - "[[src-codex-agents-config]]"
  - "[[Agent Booting Protocol]]"
  - "[[Booting Protocol Best Practices]]"
confidence: medium
---

# Context Window Management Mental Model

**Summary**
The context window is not the agent's memory. It is the current working set: the bounded space holding instructions, recent conversation, retrieved notes, tool output, and intermediate reasoning state for the task in front of it. Good operators treat context as something to shape continuously, not something to fill once and hope stays useful.

**Sources**
- [[src-claude-agents-config]]
- [[src-codex-agents-config]]
- [[Agent Booting Protocol]]
- [[Booting Protocol Best Practices]]

**Last updated**
2026-04-24

## What A Context Window Is

A context window is the bounded amount of input state a model can use for the current turn or short run of turns.

That state can include:

- system and runtime instructions
- project guidance and policy files
- the active conversation
- retrieved notes and memory
- tool output
- repeated summaries carried forward

The important point is that the context window is a working surface, not a durable store.

## What A Context Window Is Not

It is not:

- long-term memory
- a reliable archive of everything already seen
- a guarantee that whatever is present is still current
- a substitute for good retrieval or good documentation

People often say "the model knows this because it was in context earlier." That is not a safe operating assumption. Context can be truncated, displaced, diluted, or mentally overshadowed by newer material.

## The Real Unit Of Pressure

The real pressure on context is not just prompt length.

The actual load comes from the full working state:

- top-level instructions
- duplicated instructions across layers
- repo or product orientation text
- retrieved memory
- tool outputs
- logs and raw command output
- repeated restatements of the same facts
- summaries that never replaced the raw material they summarized

That is why context problems often look like "the model got sloppy" when the real issue is that too much low-value state was carried forward.

## The Core Loop

The most useful operator loop is:

```text
load
  -> work
  -> compress
  -> discard
  -> reload only what still matters
```

This is closer to how real work should happen:

- load only the narrowest context needed to start
- do a bounded piece of work
- compress what was learned into a smaller representation
- discard the bulky raw material
- reload only what is still necessary for the next step

If you skip the compress and discard steps, the context window becomes a landfill.

## Common Failure Modes

### Silent context bloat

The agent keeps carrying forward instructions, summaries, tool output, and raw notes because each piece looked individually reasonable. The session feels fine until quality drops, focus drifts, or relevant facts stop surfacing cleanly.

### Stale context treated as current truth

Old assumptions survive in the window and start acting like live state. This is especially dangerous with current config, process status, model choices, or file contents that may have changed since they were first loaded.

### Log and raw-output overload

Large command output, bundle dumps, or full transcripts crowd out higher-value working state. Raw output is sometimes necessary for inspection, but it is almost never the right thing to carry forward unchanged.

### Instruction duplication across layers

The same rule gets loaded in multiple places: runtime policy, repo docs, local notes, ad hoc chat restatement. Repetition feels safe, but duplicated instructions burn space and can create tiny wording differences that confuse precedence.

### Retrieval mistaken for boot

Dumping memory or recent notes into context is not the same as orienting the agent. Boot should be a lightweight "what matters now?" pass, not a raw retrieval flood.

## Operator Best Practices

### Search narrow first, then read narrow

Use search to identify the candidate path or line range. Only then read the specific slice. This keeps the working set shaped around the question rather than the whole repository.

### Summarize before carrying forward

If a command or note taught you something important, condense it into a short operator summary before the next step. Carry the summary, not the whole dump.

### Keep operating docs thin

Startup and policy files should point to deeper notes instead of duplicating them. Thin docs reduce drift and preserve room for task-specific state.

### Externalize durable knowledge

If something is worth knowing next session, write it into the vault or the right durable surface. Do not keep re-pasting the same lesson into fresh contexts.

### Stage retrieval

Do not front-load every possibly relevant note. Retrieve in layers: broad locator first, then the narrow page, then the exact detail only if needed.

### Treat context as a working set

Context is the task's live RAM, not the system of record. When it grows, the right response is usually compression and selective reload, not more accumulation.

## Good And Bad Patterns

### Repo exploration

Bad:
- read large files or broad directories before knowing whether they matter
- paste full diffs or wide logs into the conversation

Good:
- locate candidates with `rg --count` or `rg -l`
- inspect narrow line ranges
- carry forward a short explanation of what was learned

### Memory retrieval

Bad:
- fetch broad timelines and keep them all in play
- treat any retrieved observation as authoritative because it was "from memory"

Good:
- use staged retrieval to find only the relevant notes
- summarize the few durable facts that matter for the current task
- verify drift-prone facts before acting on them

### Tool output

Bad:
- keep full command output in context when only two lines mattered
- use logs as a substitute for diagnosis

Good:
- extract the signal, cite the command mentally or in notes, and discard the bulk
- rerun a focused command when you need fresh proof

### Boot and orientation

Bad:
- preload a huge state blob "just in case"
- confuse recent memory injection with real orientation

Good:
- begin with a thin map: where am I, what rules apply, what changed recently, what sources should I query if needed
- defer deeper retrieval until the task actually requires it

## Mapped To Your Setup

Your current stack makes the distinction between context and memory especially important:

- Claude/Codex runtime instructions shape the top layer of active working state.
- MCP retrieval gives the agent a way to fetch context on demand instead of preloading everything.
- Agents vault notes act as durable compressed knowledge that can be reloaded selectively.
- `claude-mem` is a retrieval and machine-memory layer, not the context window itself.
- Token-budget discipline is not only a cost control. It is a context-shaping policy that protects focus and reduces low-value carryover.

This is why the bounded-search rules, thin boot docs, and vault externalization habits matter operationally. They are all ways of defending context quality.

## Stable Vs Stale

The stable part of this mental model is that a context window should be managed like a bounded working set.

The stale part is the exact operational pressure profile:

- which runtime layers inject instructions automatically
- how big tool outputs tend to be
- how retrieval is exposed
- what the local team habits are

Refresh this page when your tooling, retrieval surfaces, or operating discipline changes enough to alter how context pressure actually shows up.

## Related Pages

- [[Agent Booting Protocol]]
- [[Booting Protocol Best Practices]]
- [[MCP Mental Model]]
- [[Memory Systems Mental Model]]
- [[Claude-mem in My Setup]]
