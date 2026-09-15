#!/usr/bin/env python3
"""Unit tests for validation + deployment safety (no live n8n required)."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
FIXTURES = ROOT / "tests" / "fixtures"
sys.path.insert(0, str(SRC))

from deployment.manager import WorkflowManager  # noqa: E402
from validation.secrets import find_inline_secrets  # noqa: E402
from validation.workflow import (  # noqa: E402
    load_workflow_file,
    parse_workflow_json,
    validate_workflow,
)


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class TestJsonValidity(unittest.TestCase):
    def test_valid_json(self) -> None:
        wf = load_workflow_file(FIXTURES / "valid_workflow.json")
        self.assertEqual(wf["name"], "Valid Example")
        self.assertTrue(isinstance(wf["nodes"], list))

    def test_invalid_json(self) -> None:
        with self.assertRaises(json.JSONDecodeError):
            parse_workflow_json((FIXTURES / "invalid_json.txt").read_text())


class TestSecretDetection(unittest.TestCase):
    def test_secret_detection(self) -> None:
        wf = _load("secret_workflow.json")
        findings = find_inline_secrets(wf)
        self.assertTrue(findings, "expected secret findings")
        errors = validate_workflow(wf, mode="create", remote_workflows=[])
        self.assertTrue(any("secret" in e.lower() or "bearer" in e.lower() for e in errors))


class TestWorkflowStructure(unittest.TestCase):
    def test_valid_workflow(self) -> None:
        errors = validate_workflow(_load("valid_workflow.json"), mode="create")
        self.assertEqual(errors, [])

    def test_invalid_connection(self) -> None:
        errors = validate_workflow(_load("bad_connection.json"), mode="create")
        self.assertTrue(any("target node not found" in e for e in errors))

    def test_duplicate_webhook_within_workflow(self) -> None:
        errors = validate_workflow(_load("duplicate_webhook.json"), mode="create")
        self.assertTrue(any("duplicate webhook path" in e for e in errors))

    def test_duplicate_webhook_against_remote(self) -> None:
        local = {
            "name": "New Hook",
            "nodes": [
                {
                    "parameters": {"path": "taken"},
                    "id": "w1",
                    "name": "Webhook",
                    "type": "n8n-nodes-base.webhook",
                    "typeVersion": 2,
                    "position": [0, 0],
                },
                {
                    "parameters": {},
                    "id": "s1",
                    "name": "Set",
                    "type": "n8n-nodes-base.set",
                    "typeVersion": 3.4,
                    "position": [200, 0],
                },
            ],
            "connections": {
                "Webhook": {
                    "main": [[{"node": "Set", "type": "main", "index": 0}]]
                }
            },
            "settings": {},
        }
        remotes = [
            {
                "id": "remote-1",
                "name": "Existing",
                "nodes": [
                    {
                        "type": "n8n-nodes-base.webhook",
                        "parameters": {"path": "taken"},
                        "name": "W",
                    }
                ],
            }
        ]
        errors = validate_workflow(local, mode="create", remote_workflows=remotes)
        self.assertTrue(any("webhook path" in e and "already used" in e for e in errors))

    def test_duplicate_workflow_name(self) -> None:
        wf = _load("valid_workflow.json")
        remotes = [{"id": "abc", "name": "Valid Example", "nodes": []}]
        errors = validate_workflow(wf, mode="create", remote_workflows=remotes)
        self.assertTrue(any("name already exists" in e for e in errors))


class FakeStore:
    """In-memory stand-in for n8n Public API."""

    def __init__(self) -> None:
        self.workflows: dict[str, dict] = {}
        self.create_calls = 0
        self.update_calls = 0
        self._seq = 0

    def list_enriched(self) -> list[dict]:
        return list(self.workflows.values())

    def get(self, wid: str) -> dict:
        if wid not in self.workflows:
            raise LookupError(wid)
        return json.loads(json.dumps(self.workflows[wid]))

    def create(self, payload: dict) -> dict:
        self.create_calls += 1
        self._seq += 1
        wid = f"id-{self._seq}"
        created = {
            **json.loads(json.dumps(payload)),
            "id": wid,
            "active": False,
        }
        self.workflows[wid] = created
        return created

    def update(self, wid: str, payload: dict) -> dict:
        self.update_calls += 1
        current = self.workflows[wid]
        updated = {
            **current,
            **json.loads(json.dumps(payload)),
            "id": wid,
            "active": current.get("active", False),
        }
        self.workflows[wid] = updated
        return updated


class TestDeploymentSafety(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.wf_dir = self.root / "workflows"
        self.bak_dir = self.root / "backups"
        self.wf_dir.mkdir()
        self.bak_dir.mkdir()
        self.store = FakeStore()
        # Seed an inactive remote used for update tests
        self.store.workflows["inactive-1"] = {
            "id": "inactive-1",
            "name": "Inactive Target",
            "active": False,
            "nodes": [
                {
                    "id": "n1",
                    "name": "Manual Trigger",
                    "type": "n8n-nodes-base.manualTrigger",
                    "typeVersion": 1,
                    "position": [0, 0],
                    "parameters": {},
                }
            ],
            "connections": {},
            "settings": {},
        }
        self.store.workflows["active-1"] = {
            "id": "active-1",
            "name": "Active Target",
            "active": True,
            "nodes": [
                {
                    "id": "n1",
                    "name": "Manual Trigger",
                    "type": "n8n-nodes-base.manualTrigger",
                    "typeVersion": 1,
                    "position": [0, 0],
                    "parameters": {},
                }
            ],
            "connections": {},
            "settings": {},
        }
        self.mgr = WorkflowManager(
            None,
            workflow_directory=self.wf_dir,
            backup_directory=self.bak_dir,
            create_fn=self.store.create,
            update_fn=self.store.update,
            list_fn=self.store.list_enriched,
            get_fn=self.store.get,
            skip_backup=True,
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _write_valid(self, name: str = "New Workflow") -> Path:
        data = _load("valid_workflow.json")
        data["name"] = name
        path = self.root / f"{name.replace(' ', '-').lower()}.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_dry_run_does_not_write(self) -> None:
        path = self._write_valid("Dry Run Create")
        before = self.store.create_calls
        result = self.mgr.create(path, apply=False)
        self.assertTrue(result.ok)
        self.assertFalse(result.wrote)
        self.assertFalse(result.apply)
        self.assertEqual(self.store.create_calls, before)

    def test_create_without_apply_does_not_write(self) -> None:
        path = self._write_valid("No Apply Create")
        result = self.mgr.create(path, apply=False)
        self.assertFalse(result.wrote)
        self.assertEqual(self.store.create_calls, 0)
        self.assertEqual(len(list(self.wf_dir.glob("*.json"))), 0)

    def test_create_with_apply_writes(self) -> None:
        path = self._write_valid("Applied Create")
        result = self.mgr.create(path, apply=True)
        self.assertTrue(result.ok)
        self.assertTrue(result.wrote)
        self.assertEqual(self.store.create_calls, 1)
        self.assertTrue(any(self.wf_dir.glob("*.json")))

    def test_update_without_apply_does_not_write(self) -> None:
        data = _load("valid_workflow.json")
        data["name"] = "Inactive Target"
        path = self.root / "upd-dry.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        before = self.store.update_calls
        result = self.mgr.update("inactive-1", path, apply=False)
        self.assertTrue(result.ok, result.errors)
        self.assertFalse(result.wrote)
        self.assertFalse(result.apply)
        self.assertEqual(self.store.update_calls, before)

    def test_workflow_not_found(self) -> None:
        with self.assertRaises(LookupError):
            self.mgr.resolve_remote("does-not-exist-xyz")

    def test_active_workflow_protection(self) -> None:
        path = self._write_valid("Active Target")
        # name collision with active remote is ok for update mode validation against id
        result = self.mgr.update("active-1", path, apply=True, allow_active_update=False)
        self.assertFalse(result.ok)
        self.assertFalse(result.wrote)
        self.assertEqual(self.store.update_calls, 0)
        self.assertTrue(any("is active" in e for e in result.errors))

    def test_active_override_allows_update(self) -> None:
        data = _load("valid_workflow.json")
        data["name"] = "Active Target"
        path = self.root / "active-update.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        result = self.mgr.update(
            "active-1", path, apply=True, allow_active_update=True
        )
        self.assertTrue(result.ok, result.errors)
        self.assertTrue(result.wrote)
        self.assertEqual(self.store.update_calls, 1)


class TestApiClientErrors(unittest.TestCase):
    """HTTP client error handling without a live n8n."""

    def test_connection_error(self) -> None:
        from api.client import N8nApiClient
        from unittest import mock
        import urllib.error

        client = N8nApiClient("http://127.0.0.1:9/api/v1", "fake-key", timeout=1)
        with mock.patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("Connection refused"),
        ):
            with self.assertRaises(RuntimeError) as ctx:
                client.list_workflows()
        msg = str(ctx.exception)
        self.assertIn("connection error", msg.lower())
        self.assertNotIn("fake-key", msg)

    def test_http_401_does_not_echo_body(self) -> None:
        from api.client import N8nApiClient
        from unittest import mock
        import urllib.error

        client = N8nApiClient("http://example.test/api/v1", "super-secret-key", timeout=1)

        def boom(*_a, **_k):
            raise urllib.error.HTTPError(
                "http://example.test/api/v1/workflows",
                401,
                "Unauthorized",
                hdrs=None,  # type: ignore[arg-type]
                fp=__import__("io").BytesIO(b'{"message":"n8n_api_SHOULD_NOT_LEAK"}'),
            )

        with mock.patch("urllib.request.urlopen", side_effect=boom):
            with self.assertRaises(RuntimeError) as ctx:
                client.list_workflows()
        msg = str(ctx.exception)
        self.assertIn("401", msg)
        self.assertNotIn("super-secret-key", msg)
        self.assertNotIn("SHOULD_NOT_LEAK", msg)

    def test_http_403(self) -> None:
        from api.client import N8nApiClient
        from unittest import mock
        import urllib.error

        client = N8nApiClient("http://example.test/api/v1", "k", timeout=1)

        def boom(*_a, **_k):
            raise urllib.error.HTTPError(
                "http://example.test/api/v1/workflows",
                403,
                "Forbidden",
                hdrs=None,  # type: ignore[arg-type]
                fp=__import__("io").BytesIO(b"forbidden-body"),
            )

        with mock.patch("urllib.request.urlopen", side_effect=boom):
            with self.assertRaises(RuntimeError) as ctx:
                client.list_workflows()
        self.assertIn("403", str(ctx.exception))
        self.assertNotIn("forbidden-body", str(ctx.exception))

    def test_unexpected_non_json_body(self) -> None:
        from api.client import N8nApiClient
        from unittest import mock

        class FakeResp:
            status = 200

            def read(self) -> bytes:
                return b"<html>not-json</html>"

            def __enter__(self) -> "FakeResp":
                return self

            def __exit__(self, *_a: object) -> None:
                return None

        client = N8nApiClient("http://example.test/api/v1", "k", timeout=1)
        with mock.patch("urllib.request.urlopen", return_value=FakeResp()):
            with self.assertRaises(RuntimeError) as ctx:
                client.request("GET", "/workflows")
        self.assertIn("non-JSON", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()