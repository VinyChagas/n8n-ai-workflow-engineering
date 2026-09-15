# n8n AI Workflow Engineering

Treat n8n workflows as code: validate, scan for secrets, backup, dry-run, and deploy through the n8n Public API — with safety gates that coding agents can drive from a CLI.

This project originated from the engineering of a real self-hosted automation environment where AI coding agents were used to design, validate, test and deploy production n8n workflows.

## Problem

n8n is excellent for building automations, but agent-driven changes are risky:

- JSON can be invalid or structurally broken
- Secrets can leak into workflow source
- Active workflows can be changed accidentally
- There is no built-in “pull request” loop for workflow JSON

This repository provides a small **Engineering Core** and a **CLI** that coding agents (Cursor, Claude Code, OpenAI Codex, Gemini, etc.) can call from the shell. The core does **not** depend on any specific agent product.

## Architecture

```
Cursor / Claude Code / Codex / Gemini / other agent
        │
        ▼
       CLI  (bin/n8n-workflow-manager)
        │
        ▼
ENGINEERING CORE
        ├── Validation
        ├── Secret Scan
        ├── Backup
        ├── Dry-run
        ├── Diff
        └── Approval Gates (--apply, --allow-active-update)
        │
        ▼
n8n Public API
        │
        ▼
       n8n
```

Future surfaces (not in v0.1): MCP, REST API, Web UI — all should call the same core. See [docs/MCP-ROADMAP.md](docs/MCP-ROADMAP.md).

## Quick start

Requirements: Python 3.10+, a reachable n8n instance, an API key file.

```bash
git clone https://github.com/VinyChagas/n8n-ai-workflow-engineering.git
cd n8n-ai-workflow-engineering

cp .env.example .env
mkdir -p .secrets
# Put your API key (single line) in .secrets/n8n-api-key
# chmod 600 .secrets/n8n-api-key

./bin/n8n-workflow-manager status
./bin/n8n-workflow-manager validate workflows/examples/hello-world.json --offline
./bin/n8n-workflow-manager dry-run-create workflows/examples/hello-world.json
```

Create for real only after reviewing the dry-run plan:

```bash
./bin/n8n-workflow-manager create workflows/examples/hello-world.json --apply
```

## Configuration

| Variable | Purpose | Default |
|----------|---------|---------|
| `N8N_BASE_URL` | n8n instance URL | `http://localhost:5678` |
| `N8N_API_BASE` | Optional full `/api/v1` base | derived from base URL |
| `N8N_API_KEY_FILE` | Path to API key file | `.secrets/n8n-api-key` |
| `WORKFLOW_DIRECTORY` | Local workflow JSON | `./workflows` |
| `BACKUP_DIRECTORY` | Timestamped backups | `./backups/git-backups` |
| `TEMPLATES_DIRECTORY` | Templates | `./templates` |

Recommended API key scopes: `workflow:list`, `workflow:read`, `workflow:create`, `workflow:update`. Prefer **not** granting activate/delete/execute.

See [.env.example](.env.example).

## Commands

| Command | Effect |
|---------|--------|
| `list` | List remote workflows |
| `status` | Local config + remote summary |
| `export <id\|name\|slug>` | Export one workflow to `WORKFLOW_DIRECTORY` |
| `export-all` | Export all remote workflows |
| `diff <id\|name\|slug>` | Normalized local vs remote diff |
| `backup` | Snapshot all remotes under `BACKUP_DIRECTORY` |
| `validate <file>` | Validate JSON / structure / secrets |
| `create <file>` | Plan create (**dry-run** unless `--apply`) |
| `update <wf> <file>` | Plan update (**dry-run** unless `--apply`) |
| `dry-run-create` / `dry-run-update` | Explicit dry-run aliases |

Intentionally **not** implemented: `publish`, `activate`, `deactivate`, `delete`, `execute`.

## Safety model

1. **Dry-run by default** — `create` / `update` do not write to n8n without `--apply`
2. **Backup before plan/apply** — when connected, create/update snapshot remotes into `BACKUP_DIRECTORY` even during dry-run (local disk only; n8n is unchanged)
3. **Secret scan** — inline tokens, JWTs, private keys, Bearer headers blocked
4. **Credential refs only** — `id` / `name`, never credential `data`
5. **Create stays inactive** — new workflows must not come back active
6. **Active update protection** — updating an active workflow requires `--allow-active-update`
7. **No auto-activation** — human (or explicit future command) activates after review

## Workflow lifecycle

```
Requirement → AI Analysis → Generate Workflow → Validate → Secret Scan
    → Backup → Dry-run → Create Disabled → Controlled Test
    → Inspect Execution → Export → Diff → Human Approval → Activate
```

Details: [docs/WORKFLOW-LIFECYCLE.md](docs/WORKFLOW-LIFECYCLE.md).

## AI agent usage

Any agent that can run shell commands can use this project. Example prompts:

- [examples/prompts/cursor.md](examples/prompts/cursor.md)
- [examples/prompts/claude-code.md](examples/prompts/claude-code.md)
- [examples/prompts/codex.md](examples/prompts/codex.md)

See [docs/AI-AGENTS.md](docs/AI-AGENTS.md).

## Examples

- `workflows/examples/hello-world.json` — Manual Trigger → Set
- `workflows/examples/health-monitor.json` — Schedule → Set (placeholder health check)
- `templates/minimal-manual.json` — reusable skeleton

## CLI vs API vs MCP

| Surface | Status | Role |
|---------|--------|------|
| CLI | v0.1 | Primary interface for humans and coding agents |
| Engineering Core (Python) | v0.1 | Shared validation / deployment logic |
| REST API | planned | Programmatic access wrapping the core |
| MCP | planned | Tool surface for MCP-capable agents |
| Web UI | planned | Human review / approval |

The core must remain agent-agnostic. MCP is a transport, not the product.

## Roadmap

- Stronger offline policy packs / CI github action
- Optional docker-CLI export backend for air-gapped ops
- MCP server exposing the same commands as tools
- Thin REST API and review UI
- Execution inspection helpers (read-only)

## Tests

```bash
python3 -m unittest discover -s tests -v
```

Live API tests are skipped unless `N8N_INTEGRATION=1`.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Security disclosures: [SECURITY.md](SECURITY.md).

## License

Licensed under the [Apache License 2.0](LICENSE) (`SPDX: Apache-2.0`).
