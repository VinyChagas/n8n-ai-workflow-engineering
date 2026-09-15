# Cursor prompt — n8n workflow engineering

You are helping engineer n8n workflows as code in this repository.

## Rules

1. Use `./bin/n8n-workflow-manager` for list/export/diff/backup/validate/create/update.
2. Never invent activate/delete/execute commands — they are intentionally unsupported.
3. Always `validate` then `dry-run-create` or `dry-run-update` before asking to apply.
4. Do not put secrets in workflow JSON. Use credential refs (`id`/`name`) or `$env.VAR`.
5. Do not run `create`/`update` with `--apply` unless I explicitly approve the dry-run output.
6. Updating an active workflow requires my explicit approval for `--allow-active-update`.

## Task template

Requirement: <describe automation>

Steps you should follow:

1. Draft JSON under `workflows/` or from `templates/minimal-manual.json`
2. `./bin/n8n-workflow-manager validate <file> --offline`
3. `./bin/n8n-workflow-manager dry-run-create <file>` (or dry-run-update)
4. Summarize risks and ask for approval
5. Only then: `--apply`
