"""Append-only TSV mutation log."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from penny.vault.config import VaultConfig


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class MutationRow:
    seq: int
    timestamp: str
    type: str
    entity_type: str
    entity_id: str
    payload_json: str


class MutationLog:
    """Append-only mutation log stored as TSV."""

    def __init__(self, config: VaultConfig | None = None):
        self.config = config or VaultConfig()

    @property
    def path(self) -> Path:
        return self.config.mutations_path

    def append(
        self,
        mutation_type: str,
        *,
        entity_type: str,
        entity_id: str | int | None = None,
        payload: dict[str, Any] | None = None,
        timestamp: str | None = None,
    ) -> MutationRow:
        if not self.config.is_initialized():
            self.config.initialize()

        row = MutationRow(
            seq=self.next_sequence(),
            timestamp=timestamp or _now_iso(),
            type=mutation_type,
            entity_type=entity_type,
            entity_id="" if entity_id is None else str(entity_id),
            payload_json=json.dumps(payload or {}, ensure_ascii=False, sort_keys=True),
        )

        with self.path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
            writer.writerow(
                [
                    row.seq,
                    row.timestamp,
                    row.type,
                    row.entity_type,
                    row.entity_id,
                    row.payload_json,
                ]
            )
        return row

    def list_rows(self) -> list[MutationRow]:
        if not self.path.exists():
            return []

        rows: list[MutationRow] = []
        with self.path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            for raw in reader:
                rows.append(
                    MutationRow(
                        seq=int(raw["seq"]),
                        timestamp=raw["timestamp"],
                        type=raw["type"],
                        entity_type=raw["entity_type"],
                        entity_id=raw["entity_id"],
                        payload_json=raw["payload_json"],
                    )
                )
        return rows

    def next_sequence(self) -> int:
        rows = self.list_rows()
        return 1 if not rows else rows[-1].seq + 1
