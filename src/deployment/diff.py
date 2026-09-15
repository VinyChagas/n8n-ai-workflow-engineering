"""Diff helpers for normalized workflow comparison."""
from __future__ import annotations

import json


def normalize_for_diff(wf: dict) -> str:
    keep = {
        "id": wf.get("id"),
        "name": wf.get("name"),
        "active": wf.get("active"),
        "description": wf.get("description"),
        "nodes": wf.get("nodes"),
        "connections": wf.get("connections"),
        "settings": wf.get("settings"),
        "staticData": wf.get("staticData"),
        "pinData": wf.get("pinData"),
    }
    for node in keep.get("nodes") or []:
        if not isinstance(node, dict):
            continue
        creds = node.get("credentials") or {}
        for ctype, cref in list(creds.items()):
            if isinstance(cref, dict):
                node["credentials"][ctype] = {
                    k: cref.get(k) for k in ("id", "name") if k in cref
                }
    return json.dumps(keep, indent=2, ensure_ascii=False, sort_keys=True)


def workflows_differ(left: dict, right: dict) -> bool:
    return normalize_for_diff(left) != normalize_for_diff(right)
