# MCP roadmap

MCP (Model Context Protocol) is **not implemented** in v0.1.

## Goal

Expose the same Engineering Core through multiple surfaces without forking business logic:

```
             Engineering Core
              /    |    |    \
            CLI   MCP   API   WEB
```

## Why wait?

1. Stabilize validation + safety gates in CLI first
2. Keep a single source of truth for dry-run / apply semantics
3. Avoid agent-specific shortcuts that bypass gates

## Planned MCP tools (sketch)

| Tool | Maps to |
|------|---------|
| `workflow_list` | `list` |
| `workflow_validate` | `validate` |
| `workflow_diff` | `diff` |
| `workflow_backup` | `backup` |
| `workflow_dry_run_create` | `dry-run-create` |
| `workflow_dry_run_update` | `dry-run-update` |
| `workflow_create_apply` | `create --apply` (requires explicit confirmation metadata) |
| `workflow_update_apply` | `update --apply` |

MCP tools that mutate state should still require an explicit `apply=true` argument (or equivalent), mirroring the CLI.

## Non-goals for early MCP

- Auto-activate workflows
- Credential decryption
- Unrestricted shell execution inside MCP
