"""Inline secret detection for workflow JSON source."""
from __future__ import annotations

import re
from typing import Any

SECRET_KEY_RE = re.compile(
    r"(password|passwd|secret|token|api[_-]?key|authorization|private[_-]?key|access[_-]?key)",
    re.I,
)
INLINE_SECRET_RE = re.compile(
    r"("
    r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"
    r"|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"  # jwt-like
    r"|n8n_api_[A-Za-z0-9]+"
    r")"
)
BEARER_INLINE_RE = re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", re.I)
ENV_REF_RE = re.compile(
    r"=?\s*(\{\{\s*)?\$env\.[A-Z0-9_]+\s*(\}\})?\s*"
)


def walk_strings(obj: Any, path: str = "") -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if isinstance(obj, str):
        out.append((path or "$", obj))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            out.extend(walk_strings(v, f"{path}.{k}" if path else k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.extend(walk_strings(v, f"{path}[{i}]"))
    return out


def find_inline_secrets(wf: dict) -> list[str]:
    """Return human-readable findings. Never echoes secret values."""
    errors: list[str] = []
    for path, value in walk_strings(wf):
        leaf = path.split(".")[-1]
        if INLINE_SECRET_RE.search(value):
            errors.append(f"possible inline secret at {path}")
            continue
        if SECRET_KEY_RE.search(leaf) and isinstance(value, str):
            if ENV_REF_RE.fullmatch(value):
                continue
            if value.startswith("={{") and "$env." in value and len(value) < 120:
                continue
            if value.startswith("=Bearer {{ $env.") or "Bearer {{ $env." in value:
                continue
            if len(value) >= 12 and not value.startswith("$env."):
                if not value.startswith("=") or "$env." not in value:
                    errors.append(f"possible inline secret value at {path}")
        if BEARER_INLINE_RE.search(value) and "$env." not in value:
            errors.append(f"possible inline Bearer token at {path}")
    return errors
