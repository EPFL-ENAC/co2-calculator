"""Every emission type must survive the whole way to a rendered segment.

A leaf that resolves correctly and then falls out of the stats buckets, or
reaches a chart with no label and no colour, is only half-shipped. Adding
one to ``EmissionType`` touches five places (taxonomy, generated TS mirror,
label map, i18n, colour scheme) and nothing failed when they drifted — the
#2091 leaves reached the charts as raw keys like ``neon_tubes`` sharing a
single fallback shade.

These read the frontend files directly. They are the only place that holds
both the taxonomy truth and what the charts do with it.
"""

import re
from pathlib import Path

import pytest

from app.modules.emissions.registry import (
    ORDERED_STAT_BUCKETS,
    emission_type_scope,
)
from app.modules.emissions.taxonomy import (
    ROLLUP_NODES,
    EmissionType,
    get_children,
)

FRONTEND = Path(__file__).resolve().parents[4] / "frontend" / "src"
CHARTS_TS = FRONTEND / "constant" / "charts.ts"
RESULTS_I18N = FRONTEND / "i18n" / "results.ts"
PROCESS_I18N = FRONTEND / "i18n" / "process_emissions.ts"
TAXONOMY_TS = FRONTEND / "types" / "emission-taxonomy.gen.ts"


def _object_literal(source: str, name: str) -> dict[str, str]:
    match = re.search(rf"{name}[^=]*=\s*\{{", source)
    if match is None:
        raise AssertionError(f"{name} not found — did charts.ts move?")
    body = source[match.end() : source.index("\n};", match.end())]
    return dict(re.findall(r"^\s{2}'?([A-Za-z0-9_]+)'?:\s*\n?\s*'([^']+)'", body, re.M))


def _colour_schemes(source: str) -> dict[str, set[str]]:
    blocks = re.findall(r"^    (\w+): \{(.*?)^    \},", source, re.M | re.S)
    return {
        name: set(re.findall(r"^\s+'?([A-Za-z0-9_-]+)'?:", body, re.M))
        for name, body in blocks
    }


def _leaves_by_bucket() -> list[tuple[str, bool, list[EmissionType]]]:
    out = []
    for _module, bucket_nodes in ORDERED_STAT_BUCKETS:
        leaves = [node for node in bucket_nodes.nodes if not get_children(node)]
        out.append((bucket_nodes.bucket.key, bucket_nodes.bucket.additional, leaves))
    return out


def test_generated_typescript_mirror_is_current() -> None:
    """`make gen-emission-taxonomy` was run after the last taxonomy edit."""
    ids = set(map(int, re.findall(r"^\s*(\d+):", TAXONOMY_TS.read_text(), re.M)))
    declared = {node.value for node in EmissionType.__members__.values()}
    assert ids == declared, (
        "frontend/src/types/emission-taxonomy.gen.ts is stale — run "
        "`cd backend && make gen-emission-taxonomy`. "
        f"missing={sorted(declared - ids)} stale={sorted(ids - declared)}"
    )


def test_every_emission_type_lands_in_a_stat_bucket() -> None:
    """A node outside every bucket contributes to no chart and no total."""
    bucketed = {node for _m, bn in ORDERED_STAT_BUCKETS for node in bn.nodes}
    # The two module container nodes carry no data of their own: headcount is
    # a persisted rollup, buildings splits into three buckets one level down.
    expected_orphans = {EmissionType.headcount, EmissionType.buildings}
    orphans = {
        node for node in EmissionType.__members__.values() if node not in bucketed
    }
    assert orphans == expected_orphans, (
        f"unexpected orphans: {sorted(n.name for n in orphans - expected_orphans)}"
    )


def test_no_emission_type_is_counted_by_two_buckets() -> None:
    seen: dict[EmissionType, list[str]] = {}
    for _module, bucket_nodes in ORDERED_STAT_BUCKETS:
        for node in bucket_nodes.data_nodes:
            seen.setdefault(node, []).append(bucket_nodes.bucket.key)
    doubled = {node.name: keys for node, keys in seen.items() if len(keys) > 1}
    assert not doubled, f"double-counted across buckets: {doubled}"


def test_every_data_node_carries_a_scope() -> None:
    """A scope-less data node silently drops out of the scope 1/2/3 split."""
    missing = [
        node.name
        for _module, bucket_nodes in ORDERED_STAT_BUCKETS
        for node in bucket_nodes.data_nodes
        if node not in ROLLUP_NODES and emission_type_scope(node) is None
    ]
    assert not missing, f"no GHG scope for: {sorted(missing)}"


def test_every_leaf_reaches_a_translated_label() -> None:
    """The adapter renders a leaf by its last ``__`` segment.

    Additional buckets build ``charts-<key>-subcategory`` dynamically
    (``useAdditionalCategoryCharts``); the rest go through
    ``RESULTS_SUBCATEGORY_LABEL_KEYS``. Either way an unmapped key renders
    the raw string to the user.
    """
    charts = CHARTS_TS.read_text()
    subcategory = _object_literal(charts, "RESULTS_SUBCATEGORY_LABEL_KEYS")
    category = _object_literal(charts, "RESULTS_CATEGORY_LABEL_KEYS")
    results_keys = set(re.findall(r"'([a-z0-9-]+)':\s*\{", RESULTS_I18N.read_text()))
    process_keys = set(
        re.findall(r"category\.([a-z0-9_]+)`\]", PROCESS_I18N.read_text())
    )

    unlabelled: list[str] = []
    for _bucket_key, additional, leaves in _leaves_by_bucket():
        for leaf in leaves:
            key = leaf.name.split("__")[-1]
            if additional:
                if f"charts-{key.replace('_', '-')}-subcategory" not in results_keys:
                    unlabelled.append(leaf.name)
                continue
            i18n_key = subcategory.get(key) or category.get(key)
            if i18n_key is None:
                unlabelled.append(leaf.name)
            elif i18n_key.startswith("process-emissions.category."):
                if i18n_key.rsplit(".", 1)[-1] not in process_keys:
                    unlabelled.append(leaf.name)

    assert not unlabelled, (
        f"these render as a raw key in the results charts: {sorted(unlabelled)}"
    )


@pytest.mark.parametrize(
    ("bucket_key", "additional", "leaves"),
    [case for case in _leaves_by_bucket() if case[1] and len(case[2]) > 1],
    ids=lambda value: value if isinstance(value, str) else "",
)
def test_additional_bucket_segments_have_distinct_colours(
    bucket_key: str, additional: bool, leaves: list[EmissionType]
) -> None:
    """Doughnut segments fall back to one shared shade when unmapped.

    Only buckets with more than one leaf matter — a single-segment doughnut
    is painted with the flat no-breakdown grey.
    """
    schemes = _colour_schemes(CHARTS_TS.read_text())
    scheme = schemes.get(bucket_key)
    if scheme is None:
        pytest.skip(f"no colour scheme declared for {bucket_key}")
    missing = [leaf.name for leaf in leaves if leaf.name.split("__")[-1] not in scheme]
    assert not missing, (
        f"{bucket_key}: no colour, so these collapse onto the shared "
        f"fallback shade: {sorted(missing)}"
    )
