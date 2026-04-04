"""Import archive manager for raw CSV drops."""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from penny.vault.config import VaultConfig
from penny.vault.manifests import IngestManifest, load_manifest, ManifestType


# Import directory name pattern: 000001-2026-04-04T11:19:00Z
ENTRY_PATTERN = re.compile(r"^(\d{6})-(.+)$")


@dataclass
class LogEntry:
    """A single archived import (directory with manifest + raw files)."""

    path: Path
    sequence: int
    slug: str

    @property
    def manifest_path(self) -> Path:
        """Return path to manifest.json."""
        return self.path / "manifest.json"

    def read_manifest(self) -> ManifestType:
        """Read and return the manifest."""
        return load_manifest(self.manifest_path)

    def content_files(self) -> list[Path]:
        """Return list of content files (everything except manifest.json)."""
        return [f for f in self.path.iterdir() if f.name != "manifest.json"]

    def __repr__(self) -> str:
        return f"LogEntry({self.sequence:06d}-{self.slug})"


class LogManager:
    """Manage the append-only import archive."""

    def __init__(self, config: VaultConfig):
        self.config = config

    @property
    def log_dir(self) -> Path:
        """Backward-compatible alias for the imports archive directory."""
        return self.config.imports_dir

    def _parse_entry_dir(self, path: Path) -> LogEntry | None:
        """Parse an entry directory name into a LogEntry."""
        match = ENTRY_PATTERN.match(path.name)
        if match and path.is_dir():
            return LogEntry(
                path=path,
                sequence=int(match.group(1)),
                slug=match.group(2),
            )
        return None

    def list_entries(self) -> list[LogEntry]:
        """List all log entries in sequence order."""
        if not self.log_dir.exists():
            return []

        entries = []
        for item in self.log_dir.iterdir():
            entry = self._parse_entry_dir(item)
            if entry:
                entries.append(entry)

        return sorted(entries, key=lambda e: e.sequence)

    def iter_entries(self) -> Iterator[LogEntry]:
        """Iterate over log entries in sequence order."""
        yield from self.list_entries()

    def count(self) -> int:
        """Return the number of log entries."""
        return len(self.list_entries())

    def next_sequence(self) -> int:
        """Return the next sequence number."""
        entries = self.list_entries()
        if not entries:
            return 1
        return entries[-1].sequence + 1

    def get_entry(self, sequence: int) -> LogEntry | None:
        """Get an entry by sequence number."""
        for entry in self.list_entries():
            if entry.sequence == sequence:
                return entry
        return None

    def latest_entry(self) -> LogEntry | None:
        """Return the most recent entry."""
        entries = self.list_entries()
        return entries[-1] if entries else None

    def _entry_dir_name(self, sequence: int, manifest: IngestManifest) -> str:
        """Generate entry directory name."""
        return f"{sequence:06d}-{manifest.timestamp}"

    def append(
        self,
        entry_type: str,
        manifest: IngestManifest,
        content_files: list[Path] | None = None,
    ) -> LogEntry:
        """Append a new archived import.

        Args:
            entry_type: Ignored legacy parameter kept for API compatibility.
            manifest: The import manifest to write.
            content_files: Optional files to copy into the entry directory

        Returns:
            The created LogEntry
        """
        if not self.config.is_initialized():
            self.config.initialize()

        sequence = self.next_sequence()
        dir_name = self._entry_dir_name(sequence, manifest)
        entry_path = self.log_dir / dir_name

        # Create entry directory
        entry_path.mkdir(parents=True)

        # Write manifest
        manifest.write(entry_path / "manifest.json")

        # Copy content files
        if content_files:
            for src in content_files:
                dst = entry_path / src.name
                shutil.copy2(src, dst)

        return LogEntry(
            path=entry_path,
            sequence=sequence,
            slug=manifest.timestamp,
        )

    def append_with_content(
        self,
        entry_type: str,
        manifest: IngestManifest,
        content: dict[str, str | bytes],
    ) -> LogEntry:
        """Append a new archived import with inline content.

        Args:
            entry_type: Ignored legacy parameter kept for API compatibility.
            manifest: The import manifest to write.
            content: Dict of filename -> content (str or bytes)

        Returns:
            The created LogEntry
        """
        if not self.config.is_initialized():
            self.config.initialize()

        sequence = self.next_sequence()
        dir_name = self._entry_dir_name(sequence, manifest)
        entry_path = self.log_dir / dir_name

        # Create entry directory
        entry_path.mkdir(parents=True)

        # Write manifest
        manifest.write(entry_path / "manifest.json")

        # Write content files
        for filename, data in content.items():
            filepath = entry_path / filename
            if isinstance(data, bytes):
                filepath.write_bytes(data)
            else:
                filepath.write_text(data)

        return LogEntry(
            path=entry_path,
            sequence=sequence,
            slug=manifest.timestamp,
        )
