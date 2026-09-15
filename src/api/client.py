"""n8n Public API client. Never logs API key material."""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


def load_api_key(path: str | Path) -> str:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"API key file missing: {path}")
    key = p.read_text(encoding="utf-8").strip()
    if not key:
        raise ValueError(f"API key file empty: {path}")
    return key


class N8nApiClient:
    def __init__(self, base: str, key: str, *, timeout: int = 60) -> None:
        self.base = base.rstrip("/")
        self._key = key
        self.timeout = timeout

    def request(
        self,
        method: str,
        path: str,
        body: dict | None = None,
    ) -> Any:
        url = self.base + path
        data = None
        headers = {
            "X-N8N-API-KEY": self._key,
            "Accept": "application/json",
        }
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
                if not raw:
                    return None
                try:
                    return json.loads(raw.decode("utf-8"))
                except json.JSONDecodeError:
                    raise RuntimeError(
                        f"API {method} {path} returned non-JSON body "
                        f"(status {getattr(resp, 'status', '?')}, {len(raw)} bytes)"
                    ) from None
        except urllib.error.HTTPError as exc:
            # Avoid echoing auth-challenge bodies or accidental secret reflections.
            if exc.code in (401, 403):
                raise RuntimeError(
                    f"API {method} {path} failed: HTTP {exc.code} (authentication/authorization)"
                ) from None
            err_body = exc.read().decode("utf-8", errors="replace")
            safe = err_body[:500]
            # Never retain obvious key-shaped tokens from error payloads.
            if "n8n_api_" in safe.lower() or "x-n8n-api-key" in safe.lower():
                safe = "<redacted error body>"
            raise RuntimeError(
                f"API {method} {path} failed: HTTP {exc.code}: {safe}"
            ) from None
        except urllib.error.URLError as exc:
            # Do not include full URL with potential credentials in query (we don't use any).
            raise RuntimeError(
                f"API {method} {path} connection error: {exc.reason!s}"
            ) from None

    def list_workflows(self) -> list[dict]:
        items: list[dict] = []
        cursor = None
        while True:
            q: dict[str, Any] = {"limit": 100}
            if cursor:
                q["cursor"] = cursor
            qs = urllib.parse.urlencode(q)
            data = self.request("GET", f"/workflows?{qs}")
            batch = data.get("data", []) if isinstance(data, dict) else data
            items.extend(batch or [])
            cursor = (data or {}).get("nextCursor") if isinstance(data, dict) else None
            if not cursor:
                break
        return items

    def get_workflow(self, workflow_id: str) -> dict:
        data = self.request("GET", f"/workflows/{urllib.parse.quote(workflow_id)}")
        if not isinstance(data, dict):
            raise RuntimeError("unexpected get workflow response")
        return data

    def create_workflow(self, payload: dict) -> dict:
        data = self.request("POST", "/workflows", body=payload)
        if not isinstance(data, dict):
            raise RuntimeError("unexpected create workflow response")
        return data

    def update_workflow(self, workflow_id: str, payload: dict) -> dict:
        data = self.request(
            "PUT",
            f"/workflows/{urllib.parse.quote(workflow_id)}",
            body=payload,
        )
        if not isinstance(data, dict):
            raise RuntimeError("unexpected update workflow response")
        return data

    def list_workflows_enriched(self) -> list[dict]:
        enriched: list[dict] = []
        for r in self.list_workflows():
            if r.get("nodes"):
                enriched.append(r)
            else:
                try:
                    enriched.append(self.get_workflow(r["id"]))
                except RuntimeError:
                    enriched.append(r)
        return enriched
