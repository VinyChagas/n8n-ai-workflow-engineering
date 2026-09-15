# Claude Code prompt — n8n workflow engineering

Operate this repo via the CLI. The Engineering Core is agent-agnostic; Claude Code is only a consumer.

Constraints:

- Prefer `./bin/n8n-workflow-manager …` over raw curl to n8n
- Dry-run is the default; `--apply` only after human approval
- Refuse to embed API keys, passwords, or tokens in JSON or commits
- Do not implement activate/publish/delete in scripts

Workflow:

```bash
./bin/n8n-workflow-manager status
./bin/n8n-workflow-manager validate path/to/workflow.json --offline
./bin/n8n-workflow-manager dry-run-create path/to/workflow.json
# wait for approval
./bin/n8n-workflow-manager create path/to/workflow.json --apply
./bin/n8n-workflow-manager export "<name>"
./bin/n8n-workflow-manager diff "<name>"
```

When updating production workflows that may be active, stop and ask before using `--allow-active-update`.
