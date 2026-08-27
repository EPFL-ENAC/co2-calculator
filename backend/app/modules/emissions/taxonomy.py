"""Emission taxonomy: the EmissionType tree and its traversal helpers.

Single backend source of truth for emission type IDs and parent/child
relationships. Display semantics (scope bands, chart buckets) are declared
per module as ``StatBucket``s — see ``app.modules.emissions.buckets``.
"""

import re
from enum import Enum
from typing import Protocol

# =============================================================================
# Resolution failure
# =============================================================================


class EmissionTypeResolutionError(ValueError):
    """A CSV value has no emission type, and no default may stand in for it.

    Raised by the per-module resolvers in ``app/modules/*/emissions.py``.
    Distinct from a plain ``ValueError`` because the factor-CSV provider
    lets it abort the whole upload rather than skipping the row (#2091):
    a factor filed under the wrong node produces a plausible-looking total
    that is silently wrong, which is worse than a rejected upload.
    """


_NON_TOKEN = re.compile(r"[^a-z0-9]+")


def canonical_token(value: str | None) -> str:
    """Canonicalise one CSV cell into an ``EmissionType`` name segment.

    Separator-only canonicalisation — ``"domestic waste"``,
    ``"non-ferrous metals"`` and ``"organic waste (lawn)"`` become
    ``domestic_waste``, ``non_ferrous_metals`` and ``organic_waste_lawn``,
    which is how the taxonomy already spells them. It never *chooses* a
    node: anything that does not land on a declared name still raises.
    """
    return _NON_TOKEN.sub("_", (value or "").strip().lower()).strip("_")


# =============================================================================
# EmissionType enum
# =============================================================================


class EmissionType(int, Enum):
    """Parent metadata is derived from the enum path below.

    The integer values use a positional scheme (kept for DB compatibility):
      6-digit: XX YY ZZ  (XX = category, YY = subcategory, ZZ = item)
      8-digit: XX YY ZZ WW (4th level, buildings room types)

    Use the .parent property instead of integer arithmetic.
    """

    # -------------------------------------------------------------------------
    # Additional Categories — flat leaves (no subcategory)
    # -------------------------------------------------------------------------
    food = 10000
    food__vegetarian = 10001
    food__non_vegetarian = 10002
    waste = 20000
    waste__incineration = 20001
    waste__incineration__domestic_waste = 2000101
    waste__incineration__incineration_waste_bio_chem_ani = 2000102
    waste__composting = 20002
    waste__composting__organic_waste_lawn = 2000201
    waste__biogas = 20003
    waste__biogas__organic_waste_food_leftovers = 2000301
    waste__biogas__cooking_vegetable_oil = 2000302
    waste__recycling = 20004
    waste__recycling__paper = 2000401
    waste__recycling__cardboard = 2000402
    waste__recycling__plastics = 2000403
    waste__recycling__glass = 2000404
    waste__recycling__ferrous_metals = 2000405
    waste__recycling__non_ferrous_metals = 2000406
    waste__recycling__electronics = 2000407
    waste__recycling__wood = 2000408
    waste__recycling__pet = 2000409
    waste__recycling__aluminum = 2000410
    waste__recycling__textile = 2000411
    waste__recycling__toner_and_ink_cartridges = 2000412
    waste__recycling__inert_waste = 2000413
    waste__recycling__batteries = 2000414
    waste__recycling__neon_tubes = 2000415
    waste__recycling__chemical_waste = 2000416
    commuting = 30000
    commuting__walking = 30001
    commuting__cycling = 30002
    commuting__powered_two_wheeler = 30003
    commuting__public_transport = 30004
    commuting__car = 30005

    # -------------------------------------------------------------------------
    # Headcount rollup (not part of scope/category mapping)
    # -------------------------------------------------------------------------
    headcount = 40000

    # -------------------------------------------------------------------------
    # Professional Travel
    # -------------------------------------------------------------------------
    professional_travel = 50000
    professional_travel__train = 50100
    professional_travel__train__class_1 = 50101
    professional_travel__train__class_2 = 50102
    professional_travel__plane = 50200
    professional_travel__plane__business = 50202
    professional_travel__plane__eco = 50203

    # -------------------------------------------------------------------------
    # Buildings
    # -------------------------------------------------------------------------
    buildings = 60000
    buildings__rooms = 60100

    buildings__rooms__lighting = 60101
    buildings__rooms__lighting__office = 6010101
    buildings__rooms__lighting__laboratories = 6010102
    buildings__rooms__lighting__archives = 6010103
    buildings__rooms__lighting__libraries = 6010104
    buildings__rooms__lighting__auditoriums = 6010105
    buildings__rooms__lighting__miscellaneous = 6010106

    buildings__rooms__cooling = 60102
    buildings__rooms__cooling__office = 6010201
    buildings__rooms__cooling__laboratories = 6010202
    buildings__rooms__cooling__archives = 6010203
    buildings__rooms__cooling__libraries = 6010204
    buildings__rooms__cooling__auditoriums = 6010205
    buildings__rooms__cooling__miscellaneous = 6010206

    buildings__rooms__ventilation = 60103
    buildings__rooms__ventilation__office = 6010301
    buildings__rooms__ventilation__laboratories = 6010302
    buildings__rooms__ventilation__archives = 6010303
    buildings__rooms__ventilation__libraries = 6010304
    buildings__rooms__ventilation__auditoriums = 6010305
    buildings__rooms__ventilation__miscellaneous = 6010306

    buildings__rooms__heating_electric = 60104
    buildings__rooms__heating_electric__office = 6010401
    buildings__rooms__heating_electric__laboratories = 6010402
    buildings__rooms__heating_electric__archives = 6010403
    buildings__rooms__heating_electric__libraries = 6010404
    buildings__rooms__heating_electric__auditoriums = 6010405
    buildings__rooms__heating_electric__miscellaneous = 6010406

    buildings__rooms__heating_thermal = 60105
    buildings__rooms__heating_thermal__office = 6010501
    buildings__rooms__heating_thermal__laboratories = 6010502
    buildings__rooms__heating_thermal__archives = 6010503
    buildings__rooms__heating_thermal__libraries = 6010504
    buildings__rooms__heating_thermal__auditoriums = 6010505
    buildings__rooms__heating_thermal__miscellaneous = 6010506

    buildings__combustion = 60200  # scope 1 — direct fuel combustion
    buildings__combustion__natural_gas = 60201
    buildings__combustion__heating_oil = 60202
    buildings__combustion__biomethane = 60203
    buildings__combustion__pellets = 60204
    buildings__combustion__forest_chips = 60205
    buildings__combustion__wood_logs = 60206
    buildings__combustion__propane = 60207
    buildings__construction_and_renovation = (
        60300  # scope 3 — embodied emissions of construction materials
    )

    # -------------------------------------------------------------------------
    # Process Emissions
    # -------------------------------------------------------------------------
    process_emissions = 70000
    process_emissions__ch4 = 70100
    process_emissions__co2 = 70200
    process_emissions__n2o = 70300
    process_emissions__refrigerants = 70400
    process_emissions__hfcs = 70500
    process_emissions__perfluorinated_compounds = 70600
    process_emissions__fluorinated_ethers = 70700
    process_emissions__perfluoropolyethers = 70800
    process_emissions__sf6 = 70900
    process_emissions__nf3 = 71000

    # -------------------------------------------------------------------------
    # Equipment
    # -------------------------------------------------------------------------
    equipment = 80000
    equipment__scientific = 80100
    equipment__it = 80200
    equipment__other = 80300

    # -------------------------------------------------------------------------
    # Purchases
    # -------------------------------------------------------------------------
    purchases = 90000
    purchases__goods_and_services = 90100
    purchases__scientific_equipment = 90200
    purchases__it_equipment = 90300
    purchases__consumable_accessories = 90400
    purchases__biological_chemical_gaseous = 90500
    purchases__services = 90600
    purchases__vehicles = 90700
    purchases__other = 90800
    purchases__centralized = 90900
    purchases__centralized__ln2 = 90901

    # -------------------------------------------------------------------------
    # Research Facilities
    # -------------------------------------------------------------------------
    research_facilities = 100000
    research_facilities__facilities = 100100
    research_facilities__it_facilities = 100300
    research_facilities__animal = 100200
    research_facilities__animal__rodent = 10020001
    research_facilities__animal__fish = 10020002

    # -------------------------------------------------------------------------
    # External Clouds & AI
    # -------------------------------------------------------------------------
    external = 110000
    external__clouds = 110100
    external__clouds__virtualisation = 110101
    external__clouds__calcul = 110102
    external__clouds__stockage = 110103
    external__ai = 110200
    external__ai__provider_google = 110201
    external__ai__provider_mistral_ai = 110202
    external__ai__provider_anthropic = 110203
    external__ai__provider_openai = 110204
    external__ai__provider_others = 110206
    external__ai__provider_github = 110207
    external__ai__provider_microsoft = 110208

    # -------------------------------------------------------------------------
    # Properties — derived lookups via private tables defined below
    # -------------------------------------------------------------------------

    @property
    def parent(self) -> EmissionType | None:
        pv = _PARENT_MAP.get(self.value)
        return EmissionType(pv) if pv is not None else None


# =============================================================================
# Derived taxonomy metadata
# =============================================================================


def _parent_name(name: str) -> str | None:
    parent_name, separator, _ = name.rpartition("__")
    return parent_name if separator else None


def _build_parent_map() -> dict[int, int]:
    parent_map: dict[int, int] = {}
    # `.__members__.values()` (not `for node in EmissionType`) — CodeQL's
    # non-iterable-in-for-loop check doesn't model EnumMeta.__iter__ on an
    # `int`-mixed Enum subclass, and flags a false positive otherwise.
    for node in EmissionType.__members__.values():
        parent_name = _parent_name(node.name)
        if parent_name is None:
            continue
        try:
            parent = EmissionType[parent_name]
        except KeyError:
            raise RuntimeError(
                f"Taxonomy error: {node.name} implies missing parent {parent_name!r}."
            ) from None
        parent_map[node.value] = parent.value
    return parent_map


def _build_children_map(
    parent_map: dict[int, int],
) -> dict[int, tuple[EmissionType, ...]]:
    children: dict[int, list[EmissionType]] = {}
    for node in EmissionType.__members__.values():
        parent_value = parent_map.get(node.value)
        if parent_value is not None:
            children.setdefault(parent_value, []).append(node)
    return {parent: tuple(nodes) for parent, nodes in children.items()}


_PARENT_MAP: dict[int, int] = _build_parent_map()
_CHILDREN_MAP: dict[int, tuple[EmissionType, ...]] = _build_children_map(_PARENT_MAP)

# Persisted aggregate rows: their DB values duplicate their subtree leaves,
# so stat sums must skip them to avoid double counting.
ROLLUP_NODES: frozenset[EmissionType] = frozenset(
    {
        EmissionType.headcount,
        EmissionType.professional_travel,
        EmissionType.professional_travel__train,
        EmissionType.professional_travel__plane,
        EmissionType.buildings,
        EmissionType.buildings__rooms,
        EmissionType.process_emissions,
        EmissionType.equipment,
        EmissionType.purchases,
        EmissionType.research_facilities,
        EmissionType.external,
        EmissionType.external__clouds,
        EmissionType.external__ai,
    }
)

# =============================================================================
# Tree traversal helpers
# =============================================================================


def get_children(root: EmissionType) -> list[EmissionType]:
    """Get direct children of a node (one level down)."""
    return list(_CHILDREN_MAP.get(root.value, ()))


def get_subtree_leaves(root: EmissionType) -> list[int]:
    """Get all leaf emission_type_id values under a given node (recursive)."""
    kids = get_children(root)
    if not kids:
        return [root.value]
    result: list[int] = []
    for child in kids:
        result.extend(get_subtree_leaves(child))
    return result


def get_all_nodes(root: EmissionType) -> list[EmissionType]:
    """Get all nodes (root + intermediates + leaves) under a given node."""
    result: list[EmissionType] = [root]
    kids = get_children(root)
    for child in kids:
        result.extend(get_all_nodes(child))
    return result


class FactorLike(Protocol):
    id: int | None
    classification: dict


def resolve_emission_type(emission_type_id: int) -> EmissionType | None:
    try:
        return EmissionType(emission_type_id)
    except ValueError:
        return None
