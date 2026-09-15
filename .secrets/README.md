# Place your n8n API key in this directory

Create a file named `n8n-api-key` containing only the API key (one line).

```bash
mkdir -p .secrets
chmod 700 .secrets
# write key to .secrets/n8n-api-key
chmod 600 .secrets/n8n-api-key
```

This directory is gitignored. Never commit key material.
