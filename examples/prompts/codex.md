# Codex prompt — n8n workflow engineering

Use the repository CLI as the only write path to n8n.

Goals:

- Produce valid workflow JSON
- Pass validation and secret scan
- Show dry-run plans before any apply

Commands:

```text
./bin/n8n-workflow-manager validate FILE --offline
./bin/n8n-workflow-manager dry-run-create FILE
./bin/n8n-workflow-manager dry-run-update WORKFLOW FILE
./bin/n8n-workflow-manager create FILE --apply          # only if approved
./bin/n8n-workflow-manager update WORKFLOW FILE --apply # only if approved
```

Safety:

- No secrets in source
- No activate/delete/execute
- Active updates need `--allow-active-update` plus explicit user approval

Start from `templates/minimal-manual.json` or `workflows/examples/hello-world.json` when scaffolding.
