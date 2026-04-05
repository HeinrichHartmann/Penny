"""Shared test helpers for runtime setup."""

from __future__ import annotations

import socket
from dataclasses import dataclass
from pathlib import Path

import pytest


@dataclass(frozen=True)
class FreshRuntime:
    """Fresh file-backed runtime matching the `serve-fresh` workflow."""

    root_dir: Path
    data_dir: Path
    vault_dir: Path
    port: int
    url: str


def reserve_port() -> int:
    """Reserve an ephemeral localhost port for a test runtime."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def build_fresh_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FreshRuntime:
    """Create a fresh file-backed runtime like `make serve-fresh`."""
    port = reserve_port()
    root_dir = tmp_path / f"Penny-{port}"
    data_dir = root_dir / "data"
    vault_dir = root_dir / "vault"

    monkeypatch.setenv("PENNY_DATA_DIR", str(data_dir))
    monkeypatch.setenv("PENNY_VAULT_DIR", str(vault_dir))

    return FreshRuntime(
        root_dir=root_dir,
        data_dir=data_dir,
        vault_dir=vault_dir,
        port=port,
        url=f"http://127.0.0.1:{port}",
    )
