# Security Policy

## Reporting a vulnerability

If you discover a security issue in this project (for example, secret leakage, unsafe defaults, or privilege escalation via the CLI):

1. **Do not** open a public GitHub issue with exploit details or secrets.
2. Contact the repository maintainers privately (GitHub Security Advisories preferred when enabled).
3. Include reproduction steps without pasting real credentials.

## Hard rules for contributors and agents

- Never commit API keys, passwords, tokens, private keys, or `.env` files
- Never export or commit decrypted n8n credentials
- Workflow source may reference credentials by `id`/`name` only
- Prefer `$env.VAR` or n8n credential store over inline secrets
- Create/update must remain dry-run by default

## Recommended n8n API key scopes

Grant the minimum:

- `workflow:list`
- `workflow:read`
- `workflow:create`
- `workflow:update`

Avoid granting activate/delete/execute scopes to automation agents unless you have a separate, audited process.

More detail: [docs/SECURITY.md](docs/SECURITY.md).
