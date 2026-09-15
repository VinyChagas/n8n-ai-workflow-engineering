"""Build Public API write payloads (strip read-only / secret fields)."""
from __future__ import annotations

import json
from typing import Any

ALLOWED_SETTINGS = {
    "saveExecutionProgress",
    "saveManualExecutions",
    "saveDataErrorExecution",
    "saveDataSuccessExecution",
    "executionTimeout",
    "errorWorkflow",
    "timezone",
    "executionOrder",
    "callerPolicy",
    "callerIds",
    "timeSavedPerExecution",
    "availableInMCP",
}

ALLOWED_NODE_KEYS = {
    "id",
    "name",
    "type",
    "typeVersion",
    "position",
    "parameters",
    "credentials",
    "disabled",
    "notes",
    "notesInFlow",
    "retryOnFail",
    "maxTries",
    "waitBetweenTries",
    "alwaysOutputData",
    "executeOnce",
    "continueOnFail",
    "onError",
    "webhookId",
}


def to_write_payload(wf: dict, *, for_update: bool = False) -> dict:
    """Build Public API writable payload (additionalProperties: false)."""
    del for_update  # reserved for future divergence
    raw_settings = wf.get("settings") if isinstance(wf.get("settings"), dict) else {}
    settings = {k: v for k, v in raw_settings.items() if k in ALLOWED_SETTINGS}

    payload: dict[str, Any] = {
        "name": wf.get("name"),
        "nodes": json.loads(json.dumps(wf.get("nodes") or [])),
        "connections": json.loads(json.dumps(wf.get("connections") or {})),
        "settings": settings,
    }
    if wf.get("staticData") is not None:
        payload["staticData"] = wf.get("staticData")
    if wf.get("pinData") is not None:
        payload["pinData"] = wf.get("pinData")

    cleaned_nodes = []
    for node in payload["nodes"]:
        if not isinstance(node, dict):
            continue
        n = {k: v for k, v in node.items() if k in ALLOWED_NODE_KEYS}
        creds = n.get("credentials") or {}
        if creds and isinstance(creds, dict):
            clean = {}
            for ctype, cref in creds.items():
                if isinstance(cref, dict):
                    clean[ctype] = {k: cref.get(k) for k in ("id", "name") if k in cref}
                else:
                    clean[ctype] = cref
            if clean:
                n["credentials"] = clean
            else:
                n.pop("credentials", None)
        cleaned_nodes.append(n)
    payload["nodes"] = cleaned_nodes
    return payload


def sanitize_credential_refs(wf: dict) -> dict:
    """Keep only credential id/name refs in a workflow dict (in-place copy)."""
    data = json.loads(json.dumps(wf))
    for node in data.get("nodes") or []:
        if not isinstance(node, dict):
            continue
        creds = node.get("credentials") or {}
        for ctype, cref in list(creds.items()):
            if isinstance(cref, dict):
                node["credentials"][ctype] = {
                    k: v for k, v in cref.items() if k in ("id", "name")
                }
    return data
