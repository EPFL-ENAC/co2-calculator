"""Stat buckets — the display-facing aggregation unit for emission stats.

A bucket is what the results charts render as one bar: usually a whole
module, but a module may split itself (buildings) or mark its buckets as
"additional" (headcount food/waste/commuting, buildings embodied energy),
meaning the values are informative and excluded from the organisational
total. Each module declares its buckets in its ``emissions.py``; the
emissions registry collects them in display order.
"""

from dataclasses import dataclass, field

from app.modules.emissions.taxonomy import (
    ROLLUP_NODES,
    EmissionType,
    get_all_nodes,
)


@dataclass(frozen=True)
class StatBucket:
    key: str  # stable snake_case payload key
    scope: int  # 1 | 2 | 3 — GHG scope band the chart groups by
    roots: tuple[EmissionType, ...]
    exclude: tuple[EmissionType, ...] = ()
    additional: bool = False  # additional breakdown, not in the org total


@dataclass(frozen=True)
class BucketNodes:
    """Materialised node sets for one bucket."""

    bucket: StatBucket
    nodes: tuple[EmissionType, ...] = field(default=())
    data_nodes: frozenset[EmissionType] = field(default=frozenset())


def expand_bucket(bucket: StatBucket) -> BucketNodes:
    """Materialise a bucket's subtree: all nodes, minus excluded subtrees.

    ``data_nodes`` are the nodes whose DB rows count toward the bucket total
    (everything except persisted rollup aggregates, which would double-count).
    """
    excluded: set[EmissionType] = set()
    for ex_root in bucket.exclude:
        excluded.update(get_all_nodes(ex_root))
    nodes = tuple(
        node
        for root in bucket.roots
        for node in get_all_nodes(root)
        if node not in excluded
    )
    data_nodes = frozenset(node for node in nodes if node not in ROLLUP_NODES)
    return BucketNodes(bucket=bucket, nodes=nodes, data_nodes=data_nodes)
