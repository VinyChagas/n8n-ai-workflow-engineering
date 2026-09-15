# AI agents

## Principle

The Engineering Core is **not** a Cursor plugin. Any coding agent that can:

1. edit files
2. run shell commands
3. read command output

can operate this repository.

## Recommended agent loop

1. Read requirement
2. Draft or edit workflow JSON under `workflows/` or a temp path
3. `./bin/n8n-workflow-manager validate <file> --offline`
4. `./bin/n8n-workflow-manager dry-run-create|dry-run-update …`
5. Show plan to the human
6. Only after approval: `--apply`
7. `export` + `diff` + summarize

## Do not

- Invent activate/delete commands
- Paste API keys into prompts or commits
- Skip dry-run for production instances
- Copy private workflows from a customer environment into public forks

## Prompt examples

See `examples/prompts/` for Cursor, Claude Code, and Codex starter prompts.
