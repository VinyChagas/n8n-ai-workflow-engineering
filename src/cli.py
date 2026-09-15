#!/usr/bin/env python3
"""CLI entry point for n8n-workflow-manager.

Agent-agnostic: Cursor, Claude Code, Codex, Gemini, or any shell-capable agent.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running from repo without install
_SRC = Path(__file__).resolve().parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from api.client import N8nApiClient, load_api_key
from config.settings import load_settings
from deployment.manager import WorkflowManager
from validation.workflow import load_workflow_file, validate_workflow


def die(msg: str, code: int = 1) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    raise SystemExit(code)


def build_manager() -> WorkflowManager:
    settings = load_settings()
    if not settings.n8n_api_key_file.is_file():
        die(
            f"API key file missing: {settings.n8n_api_key_file}\n"
            "Set N8N_API_KEY_FILE or create the file (see .env.example)."
        )
    try:
        key = load_api_key(settings.n8n_api_key_file)
    except (FileNotFoundError, ValueError) as exc:
        die(str(exc))
    client = N8nApiClient(settings.api_v1_base, key)
    return WorkflowManager(
        client,
        workflow_directory=settings.workflow_directory,
        backup_directory=settings.backup_directory,
    )


def cmd_status(_: argparse.Namespace) -> int:
    settings = load_settings()
    print(f"root              : {settings.root}")
    print(f"n8n base url      : {settings.n8n_base_url}")
    print(f"api v1 base       : {settings.api_v1_base}")
    print(f"api key file      : {settings.n8n_api_key_file} "
          f"({'present' if settings.n8n_api_key_file.is_file() else 'MISSING'})")
    print(f"workflows dir     : {settings.workflow_directory}")
    print(f"backup dir        : {settings.backup_directory}")
    print(f"templates dir     : {settings.templates_directory}")
    local_count = 0
    if settings.workflow_directory.is_dir():
        local_count = len(list(settings.workflow_directory.glob("*.json")))
    print(f"local JSON files  : {local_count}")

    if settings.n8n_api_key_file.is_file():
        try:
            mgr = build_manager()
            remotes = mgr._list_enriched()
            print(f"remote workflows  : {len(remotes)}")
            print("")
            print("REMOTE")
            print(f"{'ID':<24} {'ACTIVE':<8} NAME")
            for wf in remotes:
                print(
                    f"{str(wf.get('id') or ''):<24} "
                    f"{str(wf.get('active')):<8} "
                    f"{wf.get('name')}"
                )
        except Exception as exc:  # noqa: BLE001 — CLI surface
            print(f"remote status     : unavailable ({exc})")
    return 0


def cmd_list(_: argparse.Namespace) -> int:
    mgr = build_manager()
    print(f"{'ID':<24} {'ACTIVE':<8} NAME")
    print("-" * 60)
    for wf in mgr._list_enriched():
        print(
            f"{str(wf.get('id') or ''):<24} "
            f"{str(wf.get('active')):<8} "
            f"{wf.get('name')}"
        )
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    mgr = build_manager()
    dest = mgr.export_one(args.workflow)
    print(f"exported: {dest}")
    return 0


def cmd_export_all(_: argparse.Namespace) -> int:
    mgr = build_manager()
    paths = mgr.export_all()
    for p in paths:
        print(f"exported: {p.name}")
    print(f"export-all complete: {len(paths)} workflow(s)")
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    mgr = build_manager()
    identical, text = mgr.diff(args.workflow)
    print(text)
    return 0 if identical else 1


def cmd_backup(_: argparse.Namespace) -> int:
    mgr = build_manager()
    dest = mgr.backup()
    print(f"backup created: {dest}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    """Offline-first validate; optionally enrich with remote list if API configured."""
    settings = load_settings()
    try:
        wf = load_workflow_file(args.file)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        die(f"invalid workflow file: {exc}")

    remotes: list[dict] = []
    if settings.n8n_api_key_file.is_file() and not args.offline:
        try:
            mgr = build_manager()
            remotes = mgr._list_enriched()
        except Exception as exc:  # noqa: BLE001
            print(f"warning: remote enrichment skipped: {exc}", file=sys.stderr)

    errors = validate_workflow(wf, mode=args.mode, remote_workflows=remotes)
    report = {"ok": not errors, "errors": errors, "name": wf.get("name")}
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if not errors else 2


def cmd_create(args: argparse.Namespace) -> int:
    mgr = build_manager()
    result = mgr.create(args.file, apply=args.apply)
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    if not result.ok:
        return 2
    if not args.apply:
        print("DRY-RUN only. No changes applied to n8n.", file=sys.stderr)
        print("Re-run with --apply to create.", file=sys.stderr)
    return 0


def cmd_update(args: argparse.Namespace) -> int:
    mgr = build_manager()
    result = mgr.update(
        args.workflow,
        args.file,
        apply=args.apply,
        allow_active_update=args.allow_active_update,
    )
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    if not result.ok:
        # active protection uses distinct mental model; keep exit 3
        if any("is active" in e for e in result.errors):
            return 3
        return 2
    if not args.apply:
        print("DRY-RUN only. No changes applied to n8n.", file=sys.stderr)
        print("Re-run with --apply to update.", file=sys.stderr)
    return 0


def cmd_dry_run_create(args: argparse.Namespace) -> int:
    args.apply = False
    return cmd_create(args)


def cmd_dry_run_update(args: argparse.Namespace) -> int:
    args.apply = False
    args.allow_active_update = False
    return cmd_update(args)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="n8n-workflow-manager",
        description=(
            "Safe n8n workflow engineering CLI. "
            "create/update are dry-run by default; require --apply. "
            "Does not activate, publish, delete, or execute workflows."
        ),
    )
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List remote workflows").set_defaults(func=cmd_list)
    sub.add_parser("status", help="Show local config and remote summary").set_defaults(
        func=cmd_status
    )

    e = sub.add_parser("export", help="Export one workflow to WORKFLOW_DIRECTORY")
    e.add_argument("workflow")
    e.set_defaults(func=cmd_export)

    sub.add_parser("export-all", help="Export all remote workflows").set_defaults(
        func=cmd_export_all
    )

    d = sub.add_parser("diff", help="Diff local export vs remote")
    d.add_argument("workflow")
    d.set_defaults(func=cmd_diff)

    sub.add_parser("backup", help="Snapshot all remote workflows").set_defaults(
        func=cmd_backup
    )

    v = sub.add_parser("validate", help="Validate a workflow JSON file")
    v.add_argument("file")
    v.add_argument("--mode", choices=["create", "update"], default="create")
    v.add_argument("--offline", action="store_true", help="Skip remote enrichment")
    v.set_defaults(func=cmd_validate)

    c = sub.add_parser("create", help="Create workflow (dry-run unless --apply)")
    c.add_argument("file")
    c.add_argument("--apply", action="store_true")
    c.set_defaults(func=cmd_create)

    u = sub.add_parser("update", help="Update workflow (dry-run unless --apply)")
    u.add_argument("workflow")
    u.add_argument("file")
    u.add_argument("--apply", action="store_true")
    u.add_argument("--allow-active-update", action="store_true")
    u.set_defaults(func=cmd_update)

    dc = sub.add_parser("dry-run-create", help="Alias for create without --apply")
    dc.add_argument("file")
    dc.set_defaults(func=cmd_dry_run_create, apply=False)

    du = sub.add_parser("dry-run-update", help="Alias for update without --apply")
    du.add_argument("workflow")
    du.add_argument("file")
    du.set_defaults(func=cmd_dry_run_update, apply=False, allow_active_update=False)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    blocked = {"publish", "activate", "deactivate", "delete", "execute"}
    if args.command in blocked:
        die(f"command '{args.command}' is intentionally not implemented")
    try:
        return int(args.func(args))
    except (LookupError, FileNotFoundError, ValueError, RuntimeError) as exc:
        die(str(exc))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
