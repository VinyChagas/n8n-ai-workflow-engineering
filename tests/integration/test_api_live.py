"""Integration tests against a live n8n instance.

Skipped unless N8N_INTEGRATION=1 and N8N_API_KEY_FILE / N8N_BASE_URL are set.
These are intentionally separated from unit tests.
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))


@unittest.skipUnless(
    os.environ.get("N8N_INTEGRATION") == "1",
    "Set N8N_INTEGRATION=1 to run live API tests",
)
class TestLiveApi(unittest.TestCase):
    def test_list_workflows(self) -> None:
        from api.client import N8nApiClient, load_api_key
        from config.settings import load_settings

        settings = load_settings()
        key = load_api_key(settings.n8n_api_key_file)
        client = N8nApiClient(settings.api_v1_base, key)
        items = client.list_workflows()
        self.assertIsInstance(items, list)


if __name__ == "__main__":
    unittest.main()
