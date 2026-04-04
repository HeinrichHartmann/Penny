"""Vault configuration and path resolution."""

from __future__ import annotations

import os
from pathlib import Path


class VaultConfig:
    """Resolve and manage Penny's portable storage directory."""

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
    def db_path(self) -> Path:
        """Return the current-state SQLite path."""
        return self.path / "penny.sqlite"

    @property
    def imports_dir(self) -> Path:
        """Return the imports archive directory."""
        return self.path / "imports"

    @property
    def rules_dir(self) -> Path:
        """Return the directory of versioned rule snapshots."""
        return self.path / "rules"

    @property
    def mutations_path(self) -> Path:
        """Return the append-only mutation log path."""
        return self.path / "mutations.tsv"

    def exists(self) -> bool:
        """Return True if the vault directory exists."""
        return self.path.exists()

    def is_initialized(self) -> bool:
        """Return True if the portable storage structure exists."""
        return (
            self.imports_dir.exists() and self.rules_dir.exists() and self.mutations_path.exists()
        )

    def initialize(self) -> None:
        """Create the portable storage structure."""
        self.path.mkdir(parents=True, exist_ok=True)
        self.imports_dir.mkdir(exist_ok=True)
        self.rules_dir.mkdir(exist_ok=True)
        if not self.mutations_path.exists():
            self.mutations_path.write_text(
                "seq\ttimestamp\ttype\tentity_type\tentity_id\tpayload_json\n",
                encoding="utf-8",
            )

    def __repr__(self) -> str:
        return f"VaultConfig({self.path})"
