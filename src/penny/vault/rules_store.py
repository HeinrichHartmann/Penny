"""Versioned storage for Python classification rules."""

from __future__ import annotations

import importlib.resources
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from penny.vault.config import VaultConfig


def _timestamp() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _current_rules_path() -> Path:
    return Path.home() / "Penny" / "rules.py"


def _write_current_rules_copy(content: str) -> Path:
    """Atomically refresh the flattened current rules.py mirror."""
    path = _current_rules_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    tmp_fd, tmp_path = tempfile.mkstemp(dir=path.parent, prefix=".rules.py.tmp.", text=True)
    try:
        with open(tmp_fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        Path(tmp_path).replace(path)
    except Exception:
        Path(tmp_path).unlink(missing_ok=True)
        raise

    return path


def default_rules_template() -> str:
    return (
        importlib.resources.files("penny").joinpath("default_rules.py").read_text(encoding="utf-8")
    )


def latest_rules_path(config: VaultConfig | None = None) -> Path | None:
    cfg = config or VaultConfig()
    if not cfg.rules_dir.exists():
        return None
    candidates = sorted(
        cfg.rules_dir.glob("*_rules.py"),
        key=lambda path: (path.stat().st_mtime_ns, path.name),
    )
    return candidates[-1] if candidates else None


def ensure_rules_snapshot(config: VaultConfig | None = None) -> Path:
    cfg = config or VaultConfig()
    if not cfg.is_initialized():
        cfg.initialize()

    existing = latest_rules_path(cfg)
    if existing is not None:
        return existing

    path = cfg.rules_dir / f"0000_{_timestamp()}_rules.py"
    path.write_text(default_rules_template(), encoding="utf-8")
    return path


def save_rules_snapshot(content: str, config: VaultConfig | None = None) -> Path:
    """Save a rules snapshot to the rules/ directory and record in ledger."""
    from penny.vault.ledger import Ledger, LedgerEntry

    cfg = config or VaultConfig()
    if not cfg.is_initialized():
        cfg.initialize()

    ledger = Ledger(cfg.path)
    sequence = ledger.next_sequence()
    timestamp = _timestamp()

    filename = f"{sequence:04d}_{timestamp}_rules.py"
    path = cfg.rules_dir / filename
    path.write_text(content, encoding="utf-8")

    # Record in ledger
    entry = LedgerEntry(
        sequence=sequence,
        entry_type="rules",
        enabled=True,
        timestamp=timestamp,
        record={"filename": filename},
    )
    ledger.append_entry(entry)
    _write_current_rules_copy(content)

    return path
