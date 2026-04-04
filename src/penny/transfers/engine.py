"""Transfer linking engine.

Links entries that belong to the same logical transaction using
user-defined predicates and Union-Find for transitive closure.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass

from penny.transactions import Transaction


class UnionFind:
    """Union-Find data structure for grouping entries."""

    def __init__(self):
        self.parent: dict[str, str] = {}
        self.rank: dict[str, int] = {}

    def find(self, x: str) -> str:
        """Find the root of the set containing x, with path compression."""
        if x not in self.parent:
            self.parent[x] = x
            self.rank[x] = 0
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, x: str, y: str) -> None:
        """Merge the sets containing x and y."""
        root_x = self.find(x)
        root_y = self.find(y)
        if root_x == root_y:
            return
        # Union by rank
        if self.rank[root_x] < self.rank[root_y]:
            self.parent[root_x] = root_y
        elif self.rank[root_x] > self.rank[root_y]:
            self.parent[root_y] = root_x
        else:
            self.parent[root_y] = root_x
            self.rank[root_x] += 1

    def groups(self) -> dict[str, list[str]]:
        """Return all groups as a mapping of root -> members."""
        result: dict[str, list[str]] = defaultdict(list)
        for x in self.parent:
            result[self.find(x)].append(x)
        return dict(result)


@dataclass
class LinkingResult:
    """Result of the linking process."""

    # Mapping: fingerprint -> group_id
    assignments: dict[str, str]

    # Statistics
    total_entries: int
    transfer_entries: int
    groups_found: int
    grouped_entries: int
    standalone_entries: int

    # Group size distribution
    pairs: int  # groups with exactly 2 entries
    triplets: int  # groups with exactly 3 entries
    larger: int  # groups with 4+ entries
    max_group_size: int


def generate_group_id(fingerprints: list[str]) -> str:
    """Generate a deterministic group_id from member fingerprints."""
    # Sort for determinism, hash for compactness
    sorted_fps = sorted(fingerprints)
    combined = ":".join(sorted_fps)
    return hashlib.sha256(combined.encode()).hexdigest()[:16]


def link_transfers(
    entries: list[Transaction],
    predicate: Callable[[Transaction, Transaction], bool],
    prefix: str = "transfer/",
    window_days: int = 10,
) -> LinkingResult:
    """Link entries into transfer groups.

    Args:
        entries: All entries to consider
        predicate: User-defined function (a, b) -> bool
        prefix: Category prefix to filter on (default: "transfer/")
        window_days: Maximum days apart for entries to be compared

    Returns:
        LinkingResult with group assignments and statistics
    """
    # 1. Pre-filter by category prefix
    transfers = [e for e in entries if e.category and e.category.startswith(prefix)]

    # 2. Sort by date
    transfers.sort(key=lambda e: e.date)

    # 3. Sliding window comparison with Union-Find
    uf = UnionFind()

    for i, a in enumerate(transfers):
        # Initialize in Union-Find
        uf.find(a.fingerprint)

        # Look forward within window
        for j in range(i + 1, len(transfers)):
            b = transfers[j]
            days_apart = (b.date - a.date).days
            if days_apart > window_days:
                break  # Sorted, no more candidates

            # Apply user predicate
            if predicate(a, b):
                uf.union(a.fingerprint, b.fingerprint)

    # 4. Extract groups and generate group_ids
    raw_groups = uf.groups()

    # Generate deterministic group_id for each group
    assignments: dict[str, str] = {}
    for _root, members in raw_groups.items():
        if len(members) <= 1:
            continue
        group_id = generate_group_id(members)
        for fp in members:
            assignments[fp] = group_id

    # 5. Calculate statistics
    group_sizes = [len(members) for members in raw_groups.values()]
    multi_groups = [s for s in group_sizes if s > 1]

    return LinkingResult(
        assignments=assignments,
        total_entries=len(entries),
        transfer_entries=len(transfers),
        groups_found=len(multi_groups),
        grouped_entries=sum(multi_groups),
        standalone_entries=len(transfers) - sum(multi_groups),
        pairs=sum(1 for s in group_sizes if s == 2),
        triplets=sum(1 for s in group_sizes if s == 3),
        larger=sum(1 for s in group_sizes if s >= 4),
        max_group_size=max(group_sizes) if group_sizes else 0,
    )
