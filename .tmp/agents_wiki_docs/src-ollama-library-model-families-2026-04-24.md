---
type: source-summary
status: active
created: 2026-04-24
updated: 2026-04-24
tags:
  - wiki
  - source
  - ollama
  - models
sources: []
confidence: high
---

# Ollama Library Model Families 2026-04-24

**Summary**
This source summary captures a bounded slice of the official Ollama library and supporting Hugging Face pages used to ground the bootstrap-model mental model. It is intentionally selective: only the families needed to explain helper-model roles, coding-specialized helpers, and embeddings.

**Sources**
- https://ollama.com/library/llama3.2
- https://ollama.com/library/qwen2.5
- https://ollama.com/library/qwen2.5-coder
- https://ollama.com/library/nomic-embed-text
- https://huggingface.co/docs/hub/en/models-the-hub
- https://huggingface.co/collections/Qwen/qwen25
- https://huggingface.co/docs/transformers/en/quantization/bitsandbytes

**Last updated**
2026-04-24

## Why This Source Matters

The bootstrap-model note needs current, traceable model-family examples instead of vague recollection. The official Ollama library is the primary source for what is easy to run locally right now. Hugging Face is the supporting source for model-family discovery, model-card culture, and quantization concepts.

## Official Ollama Library Snapshot

- `llama3.2` is described by Ollama as Meta's small `1B` and `3B` multilingual text family, with current library tags showing about `1.3GB` for `llama3.2:1b` and `2.0GB` for `llama3.2:3b`, each with `128K` context.
- Ollama's `llama3.2` page explicitly mentions use cases such as summarization, prompt rewriting, tool use, personal information management, and multilingual retrieval, which makes it a good small-helper example.
- `qwen2.5` is listed by Ollama from `0.5B` through `72B`, with small current tags such as `398MB` for `0.5b`, `986MB` for `1.5b`, `1.9GB` for `3b`, and `4.7GB` for `7b`, each currently shown with `32K` context in the Ollama library.
- Ollama describes `qwen2.5` as strong on multilingual support, structured-data understanding, and JSON-style structured output, which makes the family a good support-model example for extraction or validation.
- `qwen2.5-coder` is listed by Ollama in `0.5B`, `1.5B`, `3B`, `7B`, `14B`, and `32B` sizes, with the smaller local tags currently shown at `398MB`, `986MB`, and `1.9GB`, each with `32K` context.
- Ollama describes `qwen2.5-coder` as focused on code generation, code reasoning, and code fixing, which makes it a good example of a task-shaped helper family.
- `nomic-embed-text` is explicitly marked by Ollama as an embedding-only model. The default tag is currently shown at about `274MB` with a `2K` context window.

## Hugging Face Support Points

- The Hugging Face Model Hub docs explain the Hub as the common hosting and discovery layer for model repositories and model cards.
- The `Qwen2.5` Hugging Face collection is a useful supporting reference because it groups the family and shows how many official size variants exist beyond whatever a local runtime chooses to expose most prominently.
- Hugging Face's `bitsandbytes` quantization docs are useful background for explaining why quantization affects operational footprint and why "same family" does not always mean "same runtime cost."

## Durable Takeaways

- For mental-model notes, use the official Ollama library for current runnable examples and current tag footprints.
- Use Hugging Face for family-level discovery, model-card context, and quantization/reference material.
- Keep the wiki selective. This note is a grounding reference, not a giant model catalog.

## Related Pages

- [[Bootstrap Models Mental Model]]
- [[ref-huggingface]]
- [[Ollama Issues in Claude-mem]]
