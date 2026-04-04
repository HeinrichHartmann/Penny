"""Penny configuration and paths."""

import os
from pathlib import Path


def default_data_dir() -> Path:
    """Return Penny's data directory."""
    override = os.environ.get("PENNY_DATA_DIR")
    if override:
        return Path(override).expanduser()

    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    if xdg_data_home:
        return Path(xdg_data_home).expanduser() / "penny"

    return Path.home() / ".local" / "share" / "penny"


def default_db_path() -> Path:
    """Return the default SQLite database path.

    The preferred location is inside the portable Penny directory.
    `PENNY_DATA_DIR` remains as a legacy fallback for older setups.
    """
    vault_dir = os.environ.get("PENNY_VAULT_DIR")
    if vault_dir:
        return Path(vault_dir).expanduser() / "penny.sqlite"

    return Path.home() / "Documents" / "Penny" / "penny.sqlite"
