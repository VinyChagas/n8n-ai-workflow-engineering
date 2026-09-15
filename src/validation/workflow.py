"""Workflow JSON validation (offline-capable)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from validation.secrets import find_inline_secrets, walk_strings

TRIGGER_TYPES = {
    "n8n-nodes-base.manualTrigger",
    "n8n-nodes-base.webhook",
    "n8n-nodes-base.scheduleTrigger",
    "n8n-nodes-base.cron",
    "n8n-nodes-base.errorTrigger",
}


def load_workflow_file(path: str | Path) -> dict:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(raw, list):
        if not raw:
            raise ValueError("workflow JSON array is empty")
        raw = raw[0]
    if not isinstance(raw, dict):
        raise ValueError("workflow JSON must be an object")
    return raw


def parse_workflow_json(text: str) -> dict:
    raw = json.loads(text)
    if isinstance(raw, list):
        if not raw:
            raise ValueError("workflow JSON array is empty")
        raw = raw[0]
    if not isinstance(raw, dict):
        raise ValueError("workflow JSON must be an object")
    return raw


def validate_workflow(
    wf: dict,
    *,
    mode: str = "create",
    remote_workflows: list[dict] | None = None,
    known_credential_ids: set[str] | None = None,
) -> list[str]:
    """Return list of error strings (empty => ok)."""
    errors: list[str] = []
    remote_workflows = remote_workflows or []

    for field in ("name", "nodes", "connections", "settings"):
        if field not in wf or wf.get(field) is None:
            errors.append(f"missing required field: {field}")

    name = wf.get("name")
    if not isinstance(name, str) or not name.strip():
        errors.append("name must be a non-empty string")

    nodes = wf.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        errors.append("nodes must be a non-empty array")
        nodes = []

    connections = wf.get("connections")
    if not isinstance(connections, dict):
        errors.append("connections must be an object")
        connections = {}

    settings = wf.get("settings")
    if settings is not None and not isinstance(settings, dict):
        errors.append("settings must be an object")

    node_names: list[str] = []
    for i, node in enumerate(nodes):
        if not isinstance(node, dict):
            errors.append(f"nodes[{i}] is not an object")
            continue
        nname = node.get("name")
        ntype = node.get("type")
        if not nname:
            errors.append(f"nodes[{i}] missing name")
        else:
            if nname in node_names:
                errors.append(f"duplicate node name: {nname}")
            node_names.append(nname)
        if not ntype:
            errors.append(f"node '{nname or i}' missing type")

        creds = node.get("credentials") or {}
        if creds and not isinstance(creds, dict):
            errors.append(f"node '{nname}' credentials must be object")
        elif isinstance(creds, dict):
            for ctype, cref in creds.items():
                if not isinstance(cref, dict):
                    errors.append(f"node '{nname}' credential '{ctype}' invalid shape")
                    continue
                extra = set(cref.keys()) - {"id", "name"}
                if extra:
                    errors.append(
                        f"node '{nname}' credential '{ctype}' has forbidden keys: {sorted(extra)}"
                    )
                if "data" in cref:
                    errors.append(
                        f"node '{nname}' credential '{ctype}' contains inline data/secret"
                    )
                cid = cref.get("id")
                if not cid:
                    errors.append(f"node '{nname}' credential '{ctype}' missing id")
                elif known_credential_ids is not None and cid not in known_credential_ids:
                    errors.append(
                        f"node '{nname}' credential id not found remotely: {cid}"
                    )

    node_name_set = set(node_names)

    for src, outs in connections.items():
        if src not in node_name_set:
            errors.append(f"connection source node not found: {src}")
        if not isinstance(outs, dict):
            errors.append(f"connections['{src}'] must be object")
            continue
        for out_name, branches in outs.items():
            if not isinstance(branches, list):
                errors.append(f"connections['{src}']['{out_name}'] must be array")
                continue
            for bi, branch in enumerate(branches):
                if not isinstance(branch, list):
                    errors.append(
                        f"connections['{src}']['{out_name}'][{bi}] must be array"
                    )
                    continue
                for ti, target in enumerate(branch):
                    if not isinstance(target, dict):
                        errors.append(
                            f"connections['{src}']['{out_name}'][{bi}][{ti}] must be object"
                        )
                        continue
                    tnode = target.get("node")
                    if tnode not in node_name_set:
                        errors.append(
                            f"connection target node not found: {tnode} (from {src})"
                        )

    targets: set[str] = set()
    for src, outs in connections.items():
        if not isinstance(outs, dict):
            continue
        for branches in outs.values():
            if not isinstance(branches, list):
                continue
            for branch in branches:
                if not isinstance(branch, list):
                    continue
                for target in branch:
                    if isinstance(target, dict) and target.get("node"):
                        targets.add(target["node"])
    sources = set(connections.keys())
    connected = sources | targets

    for node in nodes:
        if not isinstance(node, dict):
            continue
        nname = node.get("name")
        ntype = node.get("type")
        if not nname:
            continue
        if nname not in connected and len(nodes) > 1:
            if ntype not in TRIGGER_TYPES:
                errors.append(f"node without connections: {nname}")
            elif nname not in sources and len(nodes) > 1:
                errors.append(f"trigger node has no outgoing connections: {nname}")

    for path, value in walk_strings(wf):
        if value.startswith("=") and value.count("{{") != value.count("}}"):
            errors.append(f"malformed expression braces at {path}")
        if "{{" in value and value.count("{{") != value.count("}}"):
            errors.append(f"malformed mustache expression at {path}")

    errors.extend(find_inline_secrets(wf))

    if isinstance(name, str):
        for remote in remote_workflows:
            rname = remote.get("name")
            rid = remote.get("id")
            if mode == "create" and rname == name:
                errors.append(f"workflow name already exists remotely: {name} ({rid})")

    local_webhook_paths: list[str] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        if node.get("type") != "n8n-nodes-base.webhook":
            continue
        params = node.get("parameters") or {}
        path = params.get("path")
        if path:
            local_webhook_paths.append(str(path))

    if local_webhook_paths and remote_workflows:
        remote_paths: dict[str, Any] = {}
        for remote in remote_workflows:
            if mode == "update" and remote.get("id") and remote.get("id") == wf.get("id"):
                continue
            for node in remote.get("nodes") or []:
                if node.get("type") == "n8n-nodes-base.webhook":
                    p = (node.get("parameters") or {}).get("path")
                    if p:
                        remote_paths[str(p)] = remote.get("name") or remote.get("id")
        for p in local_webhook_paths:
            if p in remote_paths:
                errors.append(
                    f"webhook path '{p}' already used by workflow {remote_paths[p]}"
                )

    # Duplicate webhook paths within the same workflow
    seen_local: set[str] = set()
    for p in local_webhook_paths:
        if p in seen_local:
            errors.append(f"duplicate webhook path within workflow: {p}")
        seen_local.add(p)

    return errors
