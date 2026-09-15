"""Timestamped workflow backup snapshots."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from api.payload import sanitize_credential_refs


def slugify(name: str) -> str:
    out = []
    prev_dash = False
    for ch in name.lower():
        if ch.isalnum():
            out.append(ch)
            prev_dash = False
        else:
            if not prev_dash:
                out.append("-")
                prev_dash = True
    return "".join(out).strip("-")


def workflow_filename(name: str) -> str:
    return f"{slugify(name)}.json"


def create_backup(
    workflows: list[dict],
    backup_directory: Path,
    *,
    source: str = "n8n-public-api",
) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    dest = Path(backup_directory) / stamp
    dest.mkdir(parents=True, exist_ok=True)

    for wf in workflows:
        name = wf.get("name") or wf.get("id") or "unnamed"
        clean = sanitize_credential_refs(wf)
        path = dest / workflow_filename(str(name))
        path.write_text(
            json.dumps(clean, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    manifest_lines = [
        f"timestamp={stamp}",
        f"count={len(workflows)}",
        f"source={source}",
        "note=credential refs id/name only; no decrypted secrets",
    ]
    for wf in workflows:
        manifest_lines.append(f"workflow={wf.get('id')}|{wf.get('name')}")
    (dest / "MANIFEST.txt").write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")
    return dest
