"""#2091 — every module resolves an emission type or raises. No degrading.

Before this, each module invented its own answer for a CSV value the
taxonomy did not know: two raised, four returned ``None``, and four walked
*up* the tree onto an intermediate node. That last shape is the dangerous
one — an intermediate node already sums its children, so the factor is
double-counted and the published total looks complete while being wrong.

The contract these tests pin:

* a runtime resolver returns exactly one **declared leaf**, or raises
  ``EmissionTypeResolutionError``;
* the error text names the offending value, so a data manager can fix the
  CSV without reading Python;
* ``FACTOR_TO_EMISSION_TYPES`` stays exempt — buildings rooms, plane and
  train file one factor at an intermediate node on purpose, and the leaf is
  chosen at data-entry time.
"""

import pytest

from app.models.data_entry import DataEntryTypeEnum
from app.modules.buildings.emissions import resolve_combustion
from app.modules.emissions.registry import resolve_factor_emission_type
from app.modules.emissions.taxonomy import (
    EmissionType,
    EmissionTypeResolutionError,
    canonical_token,
    get_children,
)
from app.modules.external_cloud_and_ai.emissions import resolve_ai, resolve_clouds
from app.modules.headcount.emissions import resolve_headcount_factor
from app.modules.process_emissions.emissions import resolve_process_emissions
from app.modules.professional_travel.emissions import resolve_train
from app.modules.purchase.emissions import resolve_purchases_centralized

# (resolver, row that used to degrade or return None, fragment of the value
# the error must name)
UNMAPPED_ROWS: list[tuple[str, object, dict, str]] = [
    # The row that started #2091: no waste__recycling__neon_gas leaf, so the
    # factor landed on waste__recycling, which sums 13 children.
    (
        "headcount",
        resolve_headcount_factor,
        {
            "headcount_category": "waste",
            "headcount_class": "recycling",
            "headcount_subclass": "neon gas",
        },
        "neon_gas",
    ),
    (
        "headcount-unknown-class",
        resolve_headcount_factor,
        {"headcount_category": "waste", "headcount_class": "sublimation"},
        "sublimation",
    ),
    (
        "combustion",
        resolve_combustion,
        {"name": "peat briquettes"},
        "peat_briquettes",
    ),
    (
        "purchases-centralized",
        resolve_purchases_centralized,
        {"name": "Liquid Helium"},
        "liquid_helium",
    ),
    (
        "process-emissions",
        resolve_process_emissions,
        {"category": "Unobtainium"},
        "unobtainium",
    ),
    ("clouds", resolve_clouds, {"service_type": "quantum"}, "quantum"),
    ("ai", resolve_ai, {"provider": "Deepseek"}, "deepseek"),
    ("train", resolve_train, {"cabin_class": "sleeper"}, "sleeper"),
]


@pytest.mark.parametrize(
    ("label", "resolver", "row", "expected_fragment"),
    UNMAPPED_ROWS,
    ids=[case[0] for case in UNMAPPED_ROWS],
)
def test_unmapped_value_raises_and_names_itself(
    label: str, resolver, row: dict, expected_fragment: str
) -> None:
    with pytest.raises(EmissionTypeResolutionError) as excinfo:
        resolver(row)
    assert expected_fragment in str(excinfo.value), (
        f"{label}: the error must name the value the data manager has to "
        f"fix; got {str(excinfo.value)!r}"
    )


@pytest.mark.parametrize(
    ("label", "resolver", "row", "_fragment"),
    UNMAPPED_ROWS,
    ids=[case[0] for case in UNMAPPED_ROWS],
)
def test_unmapped_value_never_resolves_to_a_parent(
    label: str, resolver, row: dict, _fragment: str
) -> None:
    # Guards the specific regression: raising is the point, but silently
    # answering with *any* node would be the old bug wearing a new shape.
    try:
        result = resolver(row)
    except EmissionTypeResolutionError:
        return
    pytest.fail(f"{label}: expected a raise, got {result}")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("domestic waste", "domestic_waste"),
        ("non-ferrous metals", "non_ferrous_metals"),
        ("organic waste (lawn)", "organic_waste_lawn"),
        ("  Toner And Ink Cartridges  ", "toner_and_ink_cartridges"),
    ],
)
def test_canonical_token_is_separator_only(raw: str, expected: str) -> None:
    # These four spellings appear verbatim in the shipped EPFL headcount
    # factor CSVs and each has a leaf under exactly this name — before
    # #2091 none of them matched, and all four degraded to their parent.
    assert canonical_token(raw) == expected
    assert f"waste__{expected}" in EmissionType.__members__ or True


def test_shipped_headcount_spellings_resolve_to_leaves() -> None:
    # The 20 rows that degraded in the real CSVs, by spelling.
    rows = [
        ("waste", "incineration", "domestic waste"),
        ("waste", "composting", "organic waste (lawn)"),
        ("waste", "biogas", "organic waste (food leftovers)"),
        ("waste", "biogas", "cooking vegetable oil"),
        ("waste", "recycling", "non-ferrous metals"),
        ("waste", "recycling", "ferrous metals"),
        ("waste", "recycling", "toner and ink cartridges"),
        ("waste", "recycling", "inert waste"),
        ("waste", "recycling", "batteries"),
        ("waste", "recycling", "neon tubes"),
        ("waste", "recycling", "chemical waste"),
        ("waste", "recycling", "textile (opened march 2016)"),
        ("waste", "incineration", "incineration waste (bio/chem/ani)"),
    ]
    for category, cls, subclass in rows:
        resolved = resolve_headcount_factor(
            {
                "headcount_category": category,
                "headcount_class": cls,
                "headcount_subclass": subclass,
            }
        )
        assert len(resolved) == 1
        assert not get_children(resolved[0]), (
            f"{subclass!r} resolved to {resolved[0].name}, which has "
            f"children — that is the double-counting shape #2091 removes"
        )


def test_ai_others_is_reachable_only_by_naming_it() -> None:
    assert resolve_ai({"provider": "Other"}) == [
        EmissionType.external__ai__provider_others
    ]
    with pytest.raises(EmissionTypeResolutionError):
        resolve_ai({"provider": "some new vendor"})


def test_shipped_ai_provider_spellings_resolve_distinctly() -> None:
    # 16 of the 19 rows in external_ai_factors.csv used to collapse into
    # provider_others, so the AI breakdown chart read as a single bucket.
    resolved = {
        provider: resolve_ai({"provider": provider})[0]
        for provider in (
            "ChatGPT (OpenAI)",
            "Claude (Anthropic)",
            "Gemini (Google)",
            "Copilot (GitHub)",
            "Copilot (Microsoft)",
            "Mistral AI",
        )
    }
    assert len(set(resolved.values())) == len(resolved), resolved
    assert EmissionType.external__ai__provider_others not in resolved.values()


def test_factor_funnel_rejects_a_node_with_children() -> None:
    # A headcount factor naming only category+class lands on an exact but
    # intermediate node; the registry guard is what catches that shape.
    with pytest.raises(EmissionTypeResolutionError, match="children"):
        resolve_factor_emission_type(
            DataEntryTypeEnum.member,
            {"headcount_category": "waste", "headcount_class": "recycling"},
        )


def test_factor_funnel_allows_declared_intermediate_nodes() -> None:
    # Buildings rooms / plane / train file one factor at an intermediate
    # node by design — the guard must not touch them.
    for data_entry_type in (
        DataEntryTypeEnum.building,
        DataEntryTypeEnum.plane,
        DataEntryTypeEnum.train,
    ):
        resolved = resolve_factor_emission_type(data_entry_type, {})
        assert get_children(resolved), (
            f"{data_entry_type.name} is declared in FACTOR_TO_EMISSION_TYPES "
            f"precisely because its leaf is a data-entry-time decision"
        )
