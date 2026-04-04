"""Vault configuration and path resolution."""

from __future__ import annotations

import os
from pathlib import Path


class VaultConfig:
    """Resolve and manage vault directory path."""

    ENV_VAR = "PENNY_VAULT_DIR"
    DEFAULT_PATH = Path.home() / "Documents" / "Penny"

    def __init__(self, path: Path | None = None):
        """Initialize with explicit path or resolve from environment."""
        if path is not None:
            self.path = path
        else:
            self.path = self._resolve_path()

    @classmethod
    def _resolve_path(cls) -> Path:
        """Resolve vault path from environment or use default."""
        env_path = os.environ.get(cls.ENV_VAR)
        if env_path:
            return Path(env_path).expanduser()
        return cls.DEFAULT_PATH

    @property
    def log_dir(self) -> Path:
        """Return the log directory path."""
        return self.path / "log"

    def exists(self) -> bool:
        """Return True if the vault directory exists."""
        return self.path.exists()

    def is_initialized(self) -> bool:
        """Return True if the vault has been initialized (has log dir)."""
        return self.log_dir.exists()

    def initialize(self) -> None:
        """Create the vault directory structure."""
        self.path.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(exist_ok=True)

    def __repr__(self) -> str:
        return f"VaultConfig({self.path})"
