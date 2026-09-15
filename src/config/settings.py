"""Runtime configuration for n8n AI Workflow Engineering.

All environment-specific values come from environment variables or optional
dotenv files. Nothing here is tied to a particular deployment.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _project_root() -> Path:
    # src/config/settings.py -> repo root
    return Path(__file__).resolve().parents[2]


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader (no external dependency). Does not override existing env."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass(frozen=True)
class Settings:
    """Resolved configuration for the engineering core."""

    root: Path
    n8n_base_url: str
    n8n_api_key_file: Path
    workflow_directory: Path
    backup_directory: Path
    templates_directory: Path
    n8n_container: str | None
    prefer_docker_cli: bool

    @property
    def api_v1_base(self) -> str:
        base = self.n8n_base_url.rstrip("/")
        if base.endswith("/api/v1"):
            return base
        return f"{base}/api/v1"


def load_settings(env_file: str | Path | None = None) -> Settings:
    root = _project_root()
    dotenv_path = Path(env_file) if env_file else root / ".env"
    _load_dotenv(dotenv_path)

    workflow_dir = Path(
        os.environ.get("WORKFLOW_DIRECTORY", str(root / "workflows"))
    ).expanduser()
    backup_dir = Path(
        os.environ.get("BACKUP_DIRECTORY", str(root / "backups" / "git-backups"))
    ).expanduser()
    templates_dir = Path(
        os.environ.get("TEMPLATES_DIRECTORY", str(root / "templates"))
    ).expanduser()

    api_key_file = Path(
        os.environ.get(
            "N8N_API_KEY_FILE",
            str(root / ".secrets" / "n8n-api-key"),
        )
    ).expanduser()

    base_url = os.environ.get("N8N_BASE_URL", "http://localhost:5678").rstrip("/")
    # Allow explicit API base override (full /api/v1 URL)
    if os.environ.get("N8N_API_BASE"):
        base_url = os.environ["N8N_API_BASE"].rstrip("/")
        if base_url.endswith("/api/v1"):
            base_url = base_url[: -len("/api/v1")]

    container = os.environ.get("N8N_CONTAINER") or None
    prefer_docker = os.environ.get("N8N_PREFER_DOCKER_CLI", "").lower() in (
        "1",
        "true",
        "yes",
    )

    return Settings(
        root=root,
        n8n_base_url=base_url,
        n8n_api_key_file=api_key_file,
        workflow_directory=workflow_dir,
        backup_directory=backup_dir,
        templates_directory=templates_dir,
        n8n_container=container,
        prefer_docker_cli=prefer_docker,
    )
