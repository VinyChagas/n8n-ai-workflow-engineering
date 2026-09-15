# Workflow lifecycle

Recommended path from requirement to production:

```
Requirement
    ↓
AI Analysis
    ↓
Generate Workflow (JSON)
    ↓
Validate (structure, connections, expressions)
    ↓
Secret Scan
    ↓
Backup (remote snapshot)
    ↓
Dry-run (create/update plan)
    ↓
Create Disabled  (--apply)
    ↓
Controlled Test (manual run in n8n UI / isolated env)
    ↓
Inspect Execution
    ↓
Export
    ↓
Diff (local vs remote)
    ↓
Human Approval
    ↓
Activate (in n8n UI — not via this CLI in v0.1)
```

## Why create disabled?

A newly created workflow that is immediately active can fire webhooks or schedules before review. v0.1 expects create to leave workflows inactive; activation is a deliberate human step.

## Rollback

1. Locate a timestamp under `BACKUP_DIRECTORY`
2. Copy the JSON back to your working file / `WORKFLOW_DIRECTORY`
3. `dry-run-update` then `update ... --apply` (with active override only if intentional)
4. Or use n8n’s built-in version history in the UI
