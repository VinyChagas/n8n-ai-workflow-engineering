# Security

## Threats this project tries to reduce

| Threat | Mitigation |
|--------|------------|
| Agent writes broken workflow | Validation before apply |
| Secrets in JSON source | Secret scan + credential shape checks |
| Accidental production change | Dry-run default + `--apply` |
| Silent change to live automation | Refuse active update unless overridden |
| Key leakage in logs | Key file read; never print key |
| Decrypted credential export | Not implemented; discouraged |

## Secret scan heuristics

Detects (non-exhaustive):

- PEM/private key blocks
- JWT-like strings
- `n8n_api_…` style tokens
- Inline Bearer tokens without `$env`
- Sensitive field names with long literal values

Allows `$env.VAR` style references so workflows can stay secret-free in git.

## Local files that must stay private

- `.env`
- `.secrets/**`
- Live backups of private workflows (if they contain business data)
- Any decrypted credential export

`.gitignore` blocks common patterns; still review `git status` before commit.

## API key handling

```
N8N_API_KEY_FILE → read once → X-N8N-API-KEY header → never logged
```

Store the key with restrictive permissions (`chmod 600`).
