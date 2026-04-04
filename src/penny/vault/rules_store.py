"""Versioned storage for Python classification rules."""

from __future__ import annotations

import hashlib
import importlib.resources
from datetime import datetime, timezone
from pathlib import Path

from penny.vault.config import VaultConfig
from penny.vault.mutations import MutationLog


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def default_rules_template() -> str:
    return importlib.resources.files("penny").joinpath("default_rules.py").read_text(encoding="utf-8")


def latest_rules_path(config: VaultConfig | None = None) -> Path | None:
    cfg = config or VaultConfig()
    if not cfg.rules_dir.exists():
        return None
    candidates = sorted(cfg.rules_dir.glob("*_rules.py"))
    return candidates[-1] if candidates else None


def ensure_rules_snapshot(config: VaultConfig | None = None) -> Path:
    cfg = config or VaultConfig()
    if not cfg.is_initialized():
        cfg.initialize()

    existing = latest_rules_path(cfg)
    if existing is not None:
        return existing

    path = cfg.rules_dir / f"{_timestamp()}_rules.py"
    path.write_text(default_rules_template(), encoding="utf-8")
    return path


def save_rules_snapshot(content: str, config: VaultConfig | None = None) -> Path:
    cfg = config or VaultConfig()
    if not cfg.is_initialized():
        cfg.initialize()

    path = cfg.rules_dir / f"{_timestamp()}_rules.py"
    path.write_text(content, encoding="utf-8")

    MutationLog(cfg).append(
        "rules_updated",
        entity_type="rules",
        payload={
            "path": path.name,
            "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        },
    )
    return path
