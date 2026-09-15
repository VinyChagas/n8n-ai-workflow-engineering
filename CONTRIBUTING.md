# Contributing

Thanks for helping improve n8n AI Workflow Engineering.

## Principles

1. The **Engineering Core** must stay agent-agnostic (no Cursor-only APIs).
2. Prefer safety over convenience: dry-run defaults, explicit `--apply`, protect active workflows.
3. Never commit secrets, `.env`, API keys, or private workflow payloads.
4. Keep v0.x focused — avoid unrelated refactors.

## Development setup

```bash
cp .env.example .env
# optional: point at a local n8n for integration tests
python3 -m unittest discover -s tests -v
```

## Pull requests

- Include or update unit tests for validation / safety behavior
- Document new CLI flags in README and `docs/API.md`
- Do not add MCP/REST/Web until the core API for that surface is agreed

## Code layout

| Path | Role |
|------|------|
| `src/validation/` | Offline validation + secret scan |
| `src/api/` | n8n Public API client + payload shaping |
| `src/deployment/` | Backup, diff, create/update lifecycle |
| `src/config/` | Environment configuration |
| `bin/n8n-workflow-manager` | CLI launcher |
| `tests/validation/` | Unit tests (no live n8n) |
| `tests/integration/` | Optional live API tests |
