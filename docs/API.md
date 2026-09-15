# API (CLI & Core)

v0.1 exposes the Engineering Core primarily through the CLI. Python modules are importable for tests and future MCP/REST adapters.

## CLI

```bash
./bin/n8n-workflow-manager <command> [args] [flags]
```

Exit codes (common):

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Generic error |
| 2 | Validation / plan failed |
| 3 | Active workflow protection blocked update |

## Environment

See `.env.example`. `load_settings()` in `src/config/settings.py` resolves paths and URLs.

## Python core (selected)

```python
from validation.workflow import validate_workflow, load_workflow_file
from deployment.manager import WorkflowManager
from api.client import N8nApiClient
```

`WorkflowManager.create(..., apply=False)` never calls the write API.
It may still write a **local** backup snapshot under `BACKUP_DIRECTORY` before planning.
After a successful `update --apply`, `result.differed_from_proposed` may be `true` when the API
response includes server metadata not present in the proposed file; `export` + `diff`
(local vs remote, normalized) is the source of truth for convergence.

## HTTP (n8n Public API)

Used by the client:

- `GET /api/v1/workflows`
- `GET /api/v1/workflows/{id}`
- `POST /api/v1/workflows`
- `PUT /api/v1/workflows/{id}`

Header: `X-N8N-API-KEY`.

This project does not wrap activate/deactivate/delete/execute endpoints in v0.1.
