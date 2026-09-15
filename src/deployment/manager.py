"""Deployment lifecycle: dry-run, create, update with safety gates."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from api.client import N8nApiClient
from api.payload import sanitize_credential_refs, to_write_payload
from deployment.backup import create_backup, slugify, workflow_filename
from deployment.diff import normalize_for_diff, workflows_differ
from validation.workflow import load_workflow_file, validate_workflow


@dataclass
class PlanResult:
    mode: str
    apply: bool
    ok: bool
    errors: list[str] = field(default_factory=list)
    name: str | None = None
    payload_summary: dict[str, Any] = field(default_factory=dict)
    remote: dict[str, Any] | None = None
    wrote: bool = False
    result: dict[str, Any] | None = None
    backup_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "mode": self.mode,
            "apply": self.apply,
            "ok": self.ok,
            "errors": self.errors,
            "name": self.name,
            "payload_summary": self.payload_summary,
            "wrote": self.wrote,
        }
        if self.remote is not None:
            d["remote"] = self.remote
        if self.result is not None:
            d["result"] = self.result
        if self.backup_path is not None:
            d["backup_path"] = self.backup_path
        return d


WriteFn = Callable[[dict], dict]
UpdateFn = Callable[[str, dict], dict]


class WorkflowManager:
    """Engineering core for safe workflow create/update via n8n Public API."""

    def __init__(
        self,
        client: N8nApiClient | None,
        *,
        workflow_directory: Path,
        backup_directory: Path,
        create_fn: WriteFn | None = None,
        update_fn: UpdateFn | None = None,
        list_fn: Callable[[], list[dict]] | None = None,
        get_fn: Callable[[str], dict] | None = None,
        skip_backup: bool = False,
    ) -> None:
        self.client = client
        self.workflow_directory = Path(workflow_directory)
        self.backup_directory = Path(backup_directory)
        self.skip_backup = skip_backup
        self._create_fn = create_fn
        self._update_fn = update_fn
        self._list_fn = list_fn
        self._get_fn = get_fn

    def _list_enriched(self) -> list[dict]:
        if self._list_fn:
            return self._list_fn()
        assert self.client is not None
        return self.client.list_workflows_enriched()

    def _get(self, workflow_id: str) -> dict:
        if self._get_fn:
            return self._get_fn(workflow_id)
        assert self.client is not None
        return self.client.get_workflow(workflow_id)

    def _create(self, payload: dict) -> dict:
        if self._create_fn:
            return self._create_fn(payload)
        assert self.client is not None
        return self.client.create_workflow(payload)

    def _update(self, workflow_id: str, payload: dict) -> dict:
        if self._update_fn:
            return self._update_fn(workflow_id, payload)
        assert self.client is not None
        return self.client.update_workflow(workflow_id, payload)

    def resolve_remote(self, query: str) -> tuple[str, str]:
        """Resolve id|name|slug to (id, name)."""
        qslug = slugify(query)
        for wf in self._list_enriched():
            wid = str(wf.get("id") or "")
            name = str(wf.get("name") or "")
            if query == wid or query == name or qslug == slugify(name):
                return wid, name
        raise LookupError(f"workflow not found remotely: {query}")

    def plan(
        self,
        file_path: str | Path,
        *,
        mode: str,
        workflow_id: str | None = None,
        remotes: list[dict] | None = None,
    ) -> PlanResult:
        wf = load_workflow_file(file_path)
        remotes = remotes if remotes is not None else self._list_enriched()
        remote = None
        if mode == "update":
            if not workflow_id:
                raise ValueError("plan update requires workflow_id")
            remote = self._get(workflow_id)
            wf = {**wf, "id": workflow_id}

        errors = validate_workflow(wf, mode=mode, remote_workflows=remotes)
        payload = to_write_payload(wf, for_update=(mode == "update"))
        summary = {
            "name": payload.get("name"),
            "nodes": len(payload.get("nodes") or []),
            "connection_sources": len(payload.get("connections") or {}),
            "settings_keys": sorted((payload.get("settings") or {}).keys()),
            "has_credentials": any(
                bool(n.get("credentials"))
                for n in (payload.get("nodes") or [])
                if isinstance(n, dict)
            ),
        }
        result = PlanResult(
            mode=mode,
            apply=False,
            ok=not errors,
            errors=errors,
            name=wf.get("name") if isinstance(wf.get("name"), str) else None,
            payload_summary=summary,
        )
        if remote is not None:
            result.remote = {
                "id": remote.get("id"),
                "name": remote.get("name"),
                "active": remote.get("active"),
                "versionId": remote.get("versionId"),
            }
        return result

    def create(
        self,
        file_path: str | Path,
        *,
        apply: bool = False,
    ) -> PlanResult:
        remotes = self._list_enriched()
        backup_path = None
        if not self.skip_backup:
            backup_path = str(create_backup(remotes, self.backup_directory))

        plan = self.plan(file_path, mode="create", remotes=remotes)
        plan.backup_path = backup_path
        if not plan.ok:
            return plan
        if not apply:
            plan.apply = False
            plan.wrote = False
            return plan

        wf = load_workflow_file(file_path)
        payload = to_write_payload(wf, for_update=False)
        created = self._create(payload)
        if created.get("active") in (True, "true", "True"):
            plan.ok = False
            plan.errors.append(
                "safety abort: created workflow is active (unexpected)"
            )
            plan.result = {
                "id": created.get("id"),
                "name": created.get("name"),
                "active": created.get("active"),
            }
            return plan

        self.workflow_directory.mkdir(parents=True, exist_ok=True)
        dest = self.workflow_directory / workflow_filename(str(created.get("name")))
        clean = sanitize_credential_refs(created)
        dest.write_text(
            json.dumps(clean, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

        plan.apply = True
        plan.wrote = True
        plan.result = {
            "id": created.get("id"),
            "name": created.get("name"),
            "active": created.get("active"),
            "saved": str(dest),
        }
        return plan

    def update(
        self,
        query: str,
        file_path: str | Path,
        *,
        apply: bool = False,
        allow_active_update: bool = False,
    ) -> PlanResult:
        remotes = self._list_enriched()
        backup_path = None
        if not self.skip_backup:
            backup_path = str(create_backup(remotes, self.backup_directory))

        workflow_id, _name = self.resolve_remote(query)
        remote = self._get(workflow_id)

        plan = self.plan(
            file_path, mode="update", workflow_id=workflow_id, remotes=remotes
        )
        plan.backup_path = backup_path
        plan.remote = {
            "id": remote.get("id"),
            "name": remote.get("name"),
            "active": remote.get("active"),
            "versionId": remote.get("versionId"),
        }

        if remote.get("active") and not allow_active_update:
            plan.ok = False
            plan.errors.append(
                "remote workflow is active; refuse update to avoid implicit republish "
                "(pass --allow-active-update to override)"
            )
            plan.wrote = False
            return plan

        if not plan.ok:
            return plan
        if not apply:
            plan.apply = False
            plan.wrote = False
            return plan

        wf = load_workflow_file(file_path)
        payload = to_write_payload(wf, for_update=True)
        updated = self._update(workflow_id, payload)

        self.workflow_directory.mkdir(parents=True, exist_ok=True)
        resp_name = updated.get("name") or remote.get("name") or "unnamed"
        dest = self.workflow_directory / workflow_filename(str(resp_name))
        clean = sanitize_credential_refs(updated)
        dest.write_text(
            json.dumps(clean, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

        plan.apply = True
        plan.wrote = True
        plan.result = {
            "id": updated.get("id"),
            "name": updated.get("name"),
            "active": updated.get("active"),
            "saved": str(dest),
            "differed_from_proposed": workflows_differ(clean, wf),
        }
        return plan

    def export_one(self, query: str) -> Path:
        workflow_id, name = self.resolve_remote(query)
        wf = sanitize_credential_refs(self._get(workflow_id))
        self.workflow_directory.mkdir(parents=True, exist_ok=True)
        dest = self.workflow_directory / workflow_filename(name)
        dest.write_text(
            json.dumps(wf, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        return dest

    def export_all(self) -> list[Path]:
        paths: list[Path] = []
        self.workflow_directory.mkdir(parents=True, exist_ok=True)
        for wf in self._list_enriched():
            name = str(wf.get("name") or wf.get("id"))
            clean = sanitize_credential_refs(wf if wf.get("nodes") else self._get(str(wf["id"])))
            dest = self.workflow_directory / workflow_filename(name)
            dest.write_text(
                json.dumps(clean, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            paths.append(dest)
        return paths

    def backup(self) -> Path:
        return create_backup(self._list_enriched(), self.backup_directory)

    def diff(self, query: str) -> tuple[bool, str]:
        """Return (identical, unified_diff_or_message)."""
        workflow_id, name = self.resolve_remote(query)
        remote = sanitize_credential_refs(self._get(workflow_id))
        local_file = self.workflow_directory / workflow_filename(name)
        if not local_file.is_file():
            raise FileNotFoundError(f"local file missing: {local_file} (run export first)")
        local = load_workflow_file(local_file)
        left = normalize_for_diff(local)
        right = normalize_for_diff(remote)
        if left == right:
            return True, "RESULT: identical (normalized)"
        import difflib

        diff_text = "\n".join(
            difflib.unified_diff(
                left.splitlines(),
                right.splitlines(),
                fromfile="local (workflows/)",
                tofile="remote (n8n)",
                lineterm="",
            )
        )
        return False, "RESULT: differences found\n" + diff_text
