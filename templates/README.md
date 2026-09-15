# Templates

Reusable workflow skeletons. Copy, edit, validate, then create with dry-run.

## Rules

- One JSON file per template
- No inline secrets
- Credential references only as `id` / `name` (never `data`)
- Templates are not applied to n8n automatically

## Included

| File | Purpose |
|------|---------|
| `minimal-manual.json` | Manual Trigger → Set (safe smoke template) |

```bash
cp templates/minimal-manual.json /tmp/draft.json
# edit name/nodes...
./bin/n8n-workflow-manager validate /tmp/draft.json --offline
./bin/n8n-workflow-manager dry-run-create /tmp/draft.json
```
