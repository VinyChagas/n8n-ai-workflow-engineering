# Architecture

## Layers

1. **Consumers** — humans, Cursor, Claude Code, Codex, Gemini, scripts, CI
2. **CLI** — `bin/n8n-workflow-manager` → `src/cli.py`
3. **Engineering Core** — validation, secret scan, backup, dry-run, diff, gates
4. **n8n Public API** — authenticated with `X-N8N-API-KEY` from a local file
5. **n8n** — source of truth at runtime; local JSON is the versioned intent

## Module map

```
src/
  config/       Settings from env (.env optional)
  validation/   Offline structure + secret checks
  api/          HTTP client + writable payload shaping
  deployment/   Backup, diff, WorkflowManager lifecycle
  cli.py        Command surface shared by all agents
```

## Design constraints

- Core must not import Cursor/Claude/Codex SDKs
- Mutations require explicit `--apply`
- Active workflow updates require `--allow-active-update`
- Activate / delete / execute are out of scope for v0.1
- Secrets never printed (API key loaded once, never logged)

## Data flow (create)

```
JSON file
  → load + validate (+ optional remote enrichment)
  → backup remotes
  → plan (dry-run)
  → [--apply] POST /api/v1/workflows
  → assert active == false
  → export sanitized JSON to WORKFLOW_DIRECTORY
```

## Why Public API (not SQL)

Editing the n8n database directly bypasses product invariants. The Public API is the supported contract and keeps credential material out of local exports when used carefully.
