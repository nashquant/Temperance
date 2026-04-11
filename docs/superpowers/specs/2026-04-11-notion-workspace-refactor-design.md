# Notion Workspace Refactor — Design Spec

**Date:** 2026-04-11  
**Status:** Approved

## Goal

Reduce the Notion workspace to the minimum needed: a clean Home hub, active projects, a scratchpad for raw thoughts, an archive of useful reference material, and a templates section. Delete all dead weight.

---

## Target Structure

```
🏠 Home              ← rebuilt from scratch; clean landing page with 4 text links
📝 Scratchpad        ← kept as-is; thought dump to later convert to todos
🚀 Projects          ← Openclaw, Temperance, SPG Maestro (unchanged)
🗄️ Archive           ← Norwegian Training, Interview Questions, Dopamine Detox (unchanged)
📋 Templates         ← new top-level page; Reimbursement stub + tax placeholder
```

---

## Step-by-Step Changes

### 1. Delete dead-weight databases (from the current Home page)
- **My Tasks** database (`b4d5d9f3-ebb5-46f7-a43a-514b9ac8ac49`)
- **Home views** database (`0579f9fe-5990-4b8a-9b4f-779be87b2f91`)
- **New database** (`93d69d97-4bfb-448d-8f29-9bd9905ac9ed`) — unnamed
- **New database** (`36338d5208d5-4388-b563-37ea9de028b7`) — unnamed

### 2. Rebuild Home page from scratch
- Delete all existing content
- New content: short header + 4 text/link blocks pointing to Scratchpad, Projects, Archive, Templates
- No embedded databases

### 3. Create Templates page
- New top-level page: `📋 Templates`
- Sub-page: `Reimbursement` — stub with fields: Date, Amount, Description, Receipt, Status
- Sub-page: `Tax Declaration` — placeholder (empty, to be filled later)

### 4. Leave unchanged
- `📝 Scratchpad` — content stays as-is
- `🚀 Projects` and its 3 sub-pages (Openclaw, Temperance, SPG Maestro)
- `🗄️ Archive` and its 3 sub-pages (Norwegian Training, Interview Questions, Dopamine Detox)

---

## What Is NOT in Scope

- Editing content inside any project or archive page
- Setting up databases, task tracking, or any automation
- Creating a Reimbursement *database* — just a template page stub for now
