"""Data entry emission models for storing computed emission results."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, IntEnum, StrEnum
from typing import Callable, Optional, TypedDict

from sqlalchemy import Float, ForeignKey
from sqlmodel import JSON, TIMESTAMP, Column, Field, Integer, SQLModel

from app.models.data_entry import DataEntryTypeEnum

# =============================================================================
# Scope / Category metadata — source of truth for chart categorisation
# =============================================================================


class Scope(IntEnum):
    scope1 = 1
    scope2 = 2
    scope3 = 3


class EmissionCategory(StrEnum):
    # scope 1
    process_emissions = "process_emissions"
    buildings_energy_combustion = "buildings_energy_combustion"
    # scope 2
    buildings_room = "buildings_room"
    equipment = "equipment"
    # scope 3
    external_cloud_and_ai = "external_cloud_and_ai"
    purchases = "purchases"
    research_facilities = "research_facilities"
    professional_travel = "professional_travel"
    # additional breakdown
    commuting = "commuting"
    food = "food"
    waste = "waste"
    embodied_energy = "embodied_energy"


class EmissionMeta(TypedDict):
    scope: Scope
    category: EmissionCategory


# =============================================================================
# EmissionType enum
# =============================================================================


class EmissionType(int, Enum):
    """
    Explicit parent/scope/category lookup via private dicts defined below.

    The integer values use a positional scheme (kept for DB compatibility):
      6-digit: XX YY ZZ  (XX = category, YY = subcategory, ZZ = item)
      8-digit: XX YY ZZ WW (4th level, buildings room types)

    Use the .parent, .scope, .category properties instead of integer arithmetic.
    """

    # -------------------------------------------------------------------------
    # Additional Categories — flat leaves (no subcategory)
    # -------------------------------------------------------------------------
    food = 10000
    food__vegetarian = 10001
    food__non_vegetarian = 10002
    waste = 20000
    waste__incineration = 20001
    waste__composting = 20002
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
    professional_travel__plane__first = 50201
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

    buildings__rooms__heating_elec = 60104
    buildings__rooms__heating_elec__office = 6010401
    buildings__rooms__heating_elec__laboratories = 6010402
    buildings__rooms__heating_elec__archives = 6010403
    buildings__rooms__heating_elec__libraries = 6010404
    buildings__rooms__heating_elec__auditoriums = 6010405
    buildings__rooms__heating_elec__miscellaneous = 6010406

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
    buildings__embodied_energy = (
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
    purchases__additional = 90900
    purchases__additional__ln2 = 90901

    # -------------------------------------------------------------------------
    # Research Facilities
    # -------------------------------------------------------------------------
    research_facilities = 100000
    research_facilities__facilities = 100100
    research_facilities__animal = 100200
    research_facilities__animal__mice = 10020001
    research_facilities__animal__fish = 10020002
    research_facilities__it_facilities = 100300

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
    external__ai__provider_cohere = 110205
    external__ai__provider_others = 110206

    # -------------------------------------------------------------------------
    # Properties — explicit lookups via private dicts defined below
    # -------------------------------------------------------------------------

    @property
    def path(self) -> str:
        """Human-readable path derived from the enum name."""
        return self.name

    @property
    def scope(self) -> "Scope | None":
        meta = _SCOPE_CATEGORY_MAP.get(self.value)
        return meta["scope"] if meta else None

    @property
    def category(self) -> "EmissionCategory | None":
        meta = _SCOPE_CATEGORY_MAP.get(self.value)
        return meta["category"] if meta else None

    @property
    def parent(self) -> "EmissionType | None":
        pv = _PARENT_MAP.get(self.value)
        return EmissionType(pv) if pv is not None else None


# =============================================================================
# Explicit parent map — every non-root value → its parent value
# =============================================================================

_PARENT_MAP: dict[int, int] = {
    # food
    EmissionType.food__vegetarian.value: EmissionType.food.value,
    EmissionType.food__non_vegetarian.value: EmissionType.food.value,
    # waste
    EmissionType.waste__incineration.value: EmissionType.waste.value,
    EmissionType.waste__composting.value: EmissionType.waste.value,
    EmissionType.waste__biogas.value: EmissionType.waste.value,
    EmissionType.waste__biogas__organic_waste_food_leftovers.value: (
        EmissionType.waste__biogas.value
    ),
    EmissionType.waste__biogas__cooking_vegetable_oil.value: (
        EmissionType.waste__biogas.value
    ),
    EmissionType.waste__recycling.value: EmissionType.waste.value,
    EmissionType.waste__recycling__paper.value: EmissionType.waste__recycling.value,
    EmissionType.waste__recycling__cardboard.value: EmissionType.waste__recycling.value,
    EmissionType.waste__recycling__plastics.value: EmissionType.waste__recycling.value,
    EmissionType.waste__recycling__glass.value: EmissionType.waste__recycling.value,
    EmissionType.waste__recycling__ferrous_metals.value: (
        EmissionType.waste__recycling.value
    ),
    EmissionType.waste__recycling__non_ferrous_metals.value: (
        EmissionType.waste__recycling.value
    ),
    EmissionType.waste__recycling__electronics.value: (
        EmissionType.waste__recycling.value
    ),
    EmissionType.waste__recycling__wood.value: EmissionType.waste__recycling.value,
    EmissionType.waste__recycling__pet.value: EmissionType.waste__recycling.value,
    EmissionType.waste__recycling__aluminum.value: EmissionType.waste__recycling.value,
    EmissionType.waste__recycling__textile.value: EmissionType.waste__recycling.value,
    EmissionType.waste__recycling__toner_and_ink_cartridges.value: (
        EmissionType.waste__recycling.value
    ),
    EmissionType.waste__recycling__inert_waste.value: (
        EmissionType.waste__recycling.value
    ),
    # commuting
    EmissionType.commuting__walking.value: EmissionType.commuting.value,
    EmissionType.commuting__cycling.value: EmissionType.commuting.value,
    EmissionType.commuting__powered_two_wheeler.value: EmissionType.commuting.value,
    EmissionType.commuting__public_transport.value: EmissionType.commuting.value,
    EmissionType.commuting__car.value: EmissionType.commuting.value,
    # professional_travel
    EmissionType.professional_travel__train.value: (
        EmissionType.professional_travel.value
    ),
    EmissionType.professional_travel__train__class_1.value: (
        EmissionType.professional_travel__train.value
    ),
    EmissionType.professional_travel__train__class_2.value: (
        EmissionType.professional_travel__train.value
    ),
    EmissionType.professional_travel__plane.value: (
        EmissionType.professional_travel.value
    ),
    EmissionType.professional_travel__plane__first.value: (
        EmissionType.professional_travel__plane.value
    ),
    EmissionType.professional_travel__plane__business.value: (
        EmissionType.professional_travel__plane.value
    ),
    EmissionType.professional_travel__plane__eco.value: (
        EmissionType.professional_travel__plane.value
    ),
    # buildings
    EmissionType.buildings__rooms.value: EmissionType.buildings.value,
    EmissionType.buildings__rooms__lighting.value: EmissionType.buildings__rooms.value,
    EmissionType.buildings__rooms__lighting__office.value: (
        EmissionType.buildings__rooms__lighting.value
    ),
    EmissionType.buildings__rooms__lighting__laboratories.value: (
        EmissionType.buildings__rooms__lighting.value
    ),
    EmissionType.buildings__rooms__lighting__archives.value: (
        EmissionType.buildings__rooms__lighting.value
    ),
    EmissionType.buildings__rooms__lighting__libraries.value: (
        EmissionType.buildings__rooms__lighting.value
    ),
    EmissionType.buildings__rooms__lighting__auditoriums.value: (
        EmissionType.buildings__rooms__lighting.value
    ),
    EmissionType.buildings__rooms__lighting__miscellaneous.value: (
        EmissionType.buildings__rooms__lighting.value
    ),
    EmissionType.buildings__rooms__cooling.value: EmissionType.buildings__rooms.value,
    EmissionType.buildings__rooms__cooling__office.value: (
        EmissionType.buildings__rooms__cooling.value
    ),
    EmissionType.buildings__rooms__cooling__laboratories.value: (
        EmissionType.buildings__rooms__cooling.value
    ),
    EmissionType.buildings__rooms__cooling__archives.value: (
        EmissionType.buildings__rooms__cooling.value
    ),
    EmissionType.buildings__rooms__cooling__libraries.value: (
        EmissionType.buildings__rooms__cooling.value
    ),
    EmissionType.buildings__rooms__cooling__auditoriums.value: (
        EmissionType.buildings__rooms__cooling.value
    ),
    EmissionType.buildings__rooms__cooling__miscellaneous.value: (
        EmissionType.buildings__rooms__cooling.value
    ),
    EmissionType.buildings__rooms__ventilation.value: (
        EmissionType.buildings__rooms.value
    ),
    EmissionType.buildings__rooms__ventilation__office.value: (
        EmissionType.buildings__rooms__ventilation.value
    ),
    EmissionType.buildings__rooms__ventilation__laboratories.value: (
        EmissionType.buildings__rooms__ventilation.value
    ),
    EmissionType.buildings__rooms__ventilation__archives.value: (
        EmissionType.buildings__rooms__ventilation.value
    ),
    EmissionType.buildings__rooms__ventilation__libraries.value: (
        EmissionType.buildings__rooms__ventilation.value
    ),
    EmissionType.buildings__rooms__ventilation__auditoriums.value: (
        EmissionType.buildings__rooms__ventilation.value
    ),
    EmissionType.buildings__rooms__ventilation__miscellaneous.value: (
        EmissionType.buildings__rooms__ventilation.value
    ),
    EmissionType.buildings__rooms__heating_elec.value: (
        EmissionType.buildings__rooms.value
    ),
    EmissionType.buildings__rooms__heating_elec__office.value: (
        EmissionType.buildings__rooms__heating_elec.value
    ),
    EmissionType.buildings__rooms__heating_elec__laboratories.value: (
        EmissionType.buildings__rooms__heating_elec.value
    ),
    EmissionType.buildings__rooms__heating_elec__archives.value: (
        EmissionType.buildings__rooms__heating_elec.value
    ),
    EmissionType.buildings__rooms__heating_elec__libraries.value: (
        EmissionType.buildings__rooms__heating_elec.value
    ),
    EmissionType.buildings__rooms__heating_elec__auditoriums.value: (
        EmissionType.buildings__rooms__heating_elec.value
    ),
    EmissionType.buildings__rooms__heating_elec__miscellaneous.value: (
        EmissionType.buildings__rooms__heating_elec.value
    ),
    EmissionType.buildings__rooms__heating_thermal.value: (
        EmissionType.buildings__rooms.value
    ),
    EmissionType.buildings__rooms__heating_thermal__office.value: (
        EmissionType.buildings__rooms__heating_thermal.value
    ),
    EmissionType.buildings__rooms__heating_thermal__laboratories.value: (
        EmissionType.buildings__rooms__heating_thermal.value
    ),
    EmissionType.buildings__rooms__heating_thermal__archives.value: (
        EmissionType.buildings__rooms__heating_thermal.value
    ),
    EmissionType.buildings__rooms__heating_thermal__libraries.value: (
        EmissionType.buildings__rooms__heating_thermal.value
    ),
    EmissionType.buildings__rooms__heating_thermal__auditoriums.value: (
        EmissionType.buildings__rooms__heating_thermal.value
    ),
    EmissionType.buildings__rooms__heating_thermal__miscellaneous.value: (
        EmissionType.buildings__rooms__heating_thermal.value
    ),
    EmissionType.buildings__combustion.value: EmissionType.buildings.value,
    EmissionType.buildings__combustion__natural_gas.value: (
        EmissionType.buildings__combustion.value
    ),
    EmissionType.buildings__combustion__heating_oil.value: (
        EmissionType.buildings__combustion.value
    ),
    EmissionType.buildings__combustion__biomethane.value: (
        EmissionType.buildings__combustion.value
    ),
    EmissionType.buildings__combustion__pellets.value: (
        EmissionType.buildings__combustion.value
    ),
    EmissionType.buildings__combustion__forest_chips.value: (
        EmissionType.buildings__combustion.value
    ),
    EmissionType.buildings__combustion__wood_logs.value: (
        EmissionType.buildings__combustion.value
    ),
    EmissionType.buildings__embodied_energy.value: EmissionType.buildings.value,
    # process_emissions
    EmissionType.process_emissions__ch4.value: EmissionType.process_emissions.value,
    EmissionType.process_emissions__co2.value: EmissionType.process_emissions.value,
    EmissionType.process_emissions__n2o.value: EmissionType.process_emissions.value,
    EmissionType.process_emissions__refrigerants.value: (
        EmissionType.process_emissions.value
    ),
    # equipment
    EmissionType.equipment__scientific.value: EmissionType.equipment.value,
    EmissionType.equipment__it.value: EmissionType.equipment.value,
    EmissionType.equipment__other.value: EmissionType.equipment.value,
    # purchases
    EmissionType.purchases__goods_and_services.value: EmissionType.purchases.value,
    EmissionType.purchases__scientific_equipment.value: EmissionType.purchases.value,
    EmissionType.purchases__it_equipment.value: EmissionType.purchases.value,
    EmissionType.purchases__consumable_accessories.value: EmissionType.purchases.value,
    EmissionType.purchases__biological_chemical_gaseous.value: (
        EmissionType.purchases.value
    ),
    EmissionType.purchases__services.value: EmissionType.purchases.value,
    EmissionType.purchases__vehicles.value: EmissionType.purchases.value,
    EmissionType.purchases__other.value: EmissionType.purchases.value,
    EmissionType.purchases__additional.value: EmissionType.purchases.value,
    EmissionType.purchases__additional__ln2.value: (
        EmissionType.purchases__additional.value
    ),
    # research_facilities
    EmissionType.research_facilities__facilities.value: (
        EmissionType.research_facilities.value
    ),
    EmissionType.research_facilities__animal.value: (
        EmissionType.research_facilities.value
    ),
    EmissionType.research_facilities__animal__mice.value: (
        EmissionType.research_facilities__animal.value
    ),
    EmissionType.research_facilities__animal__fish.value: (
        EmissionType.research_facilities__animal.value
    ),
    EmissionType.research_facilities__it_facilities.value: (
        EmissionType.research_facilities.value
    ),
    # external
    EmissionType.external__clouds.value: EmissionType.external.value,
    EmissionType.external__clouds__virtualisation.value: (
        EmissionType.external__clouds.value
    ),
    EmissionType.external__clouds__calcul.value: EmissionType.external__clouds.value,
    EmissionType.external__clouds__stockage.value: EmissionType.external__clouds.value,
    EmissionType.external__ai.value: EmissionType.external.value,
    EmissionType.external__ai__provider_google.value: EmissionType.external__ai.value,
    EmissionType.external__ai__provider_mistral_ai.value: (
        EmissionType.external__ai.value
    ),
    EmissionType.external__ai__provider_anthropic.value: (
        EmissionType.external__ai.value
    ),
    EmissionType.external__ai__provider_openai.value: EmissionType.external__ai.value,
    EmissionType.external__ai__provider_cohere.value: EmissionType.external__ai.value,
    EmissionType.external__ai__provider_others.value: EmissionType.external__ai.value,
}

# =============================================================================
# Scope/category map — only nodes that represent actual data rows
# =============================================================================

_SCOPE_CATEGORY_MAP: dict[int, EmissionMeta] = {
    # Additional Categories — scope 3
    EmissionType.food.value: {"scope": Scope.scope3, "category": EmissionCategory.food},
    EmissionType.food__vegetarian.value: {
        "scope": Scope.scope3,
        "category": EmissionCategory.food,
    },
    EmissionType.food__non_vegetarian.value: {
        "scope": Scope.scope3,
        "category": EmissionCategory.food,
    },
    EmissionType.waste.value: {
        "scope": Scope.scope3,
        "category": EmissionCategory.waste,
    },
    EmissionType.waste__incineration.value: {
        "scope": Scope.scope3,
        "category": EmissionCategory.waste,
    },
    EmissionType.waste__composting.value: {
        "scope": Scope.scope3,
        "category": EmissionCategory.waste,
    },
    EmissionType.waste__biogas.value: {
        "scope": Scope.scope3,
        "category": EmissionCategory.waste,
    },
    EmissionType.waste__biogas__organic_waste_food_leftovers.value: {
        "scope": Scope.scope3,
        "category": EmissionCategory.waste,
    },
    EmissionType.waste__biogas__cooking_vegetable_oil.value: {
        "scope": Scope.scope3,
        "category": EmissionCategory.waste,
    },
    EmissionType.waste__recycling.value: {
        "scope": Scope.scope3,
        "category": EmissionCategory.waste,
    },
    EmissionType.waste__recycling__paper.value: {
        "scope": Scope.scope3,
        "category": EmissionCategory.waste,
    },
    EmissionType.waste__recycling__cardboard.value: {
        "scope": Scope.scope3,
        "category": EmissionCategory.waste,
    },
    EmissionType.waste__recycling__plastics.value: {
        "scope": Scope.scope3,
        "category": EmissionCategory.waste,
    },
    EmissionType.waste__recycling__glass.value: {
        "scope": Scope.scope3,
        "category": EmissionCategory.waste,
    },
    EmissionType.waste__recycling__ferrous_metals.value: {
        "scope": Scope.scope3,
        "category": EmissionCategory.waste,
    },
    EmissionType.waste__recycling__non_ferrous_metals.value: {
        "scope": Scope.scope3,
        "category": EmissionCategory.waste,
    },
    EmissionType.waste__recycling__electronics.value: {
        "scope": Scope.scope3,
        "category": EmissionCategory.waste,
    },
    EmissionType.waste__recycling__wood.value: {
        "scope": Scope.scope3,
        "category": EmissionCategory.waste,
    },
    EmissionType.waste__recycling__pet.value: {
        "scope": Scope.scope3,
        "category": EmissionCategory.waste,
    },
    EmissionType.waste__recycling__aluminum.value: {
        "scope": Scope.scope3,
        "category": EmissionCategory.waste,
    },
    EmissionType.waste__recycling__textile.value: {
        "scope": Scope.scope3,
        "category": EmissionCategory.waste,
    },
    EmissionType.waste__recycling__toner_and_ink_cartridges.value: {
        "scope": Scope.scope3,
        "category": EmissionCategory.waste,
    },
    EmissionType.waste__recycling__inert_waste.value: {
        "scope": Scope.scope3,
        "category": EmissionCategory.waste,
    },
    EmissionType.commuting.value: {
        "scope": Scope.scope3,
        "category": EmissionCategory.commuting,
    },
    EmissionType.commuting__walking.value: {
        "scope": Scope.scope3,
        "category": EmissionCategory.commuting,
    },
    EmissionType.commuting__cycling.value: {
        "scope": Scope.scope3,
        "category": EmissionCategory.commuting,
    },
    EmissionType.commuting__powered_two_wheeler.value: {
        "scope": Scope.scope3,
        "category": EmissionCategory.commuting,
    },
    EmissionType.commuting__public_transport.value: {
        "scope": Scope.scope3,
        "category": EmissionCategory.commuting,
    },
    EmissionType.commuting__car.value: {
        "scope": Scope.scope3,
        "category": EmissionCategory.commuting,
    },
    # Professional Travel — all scope 3
    EmissionType.professional_travel__train__class_1.value: {
        "scope": Scope.scope3,
        "category": EmissionCategory.professional_travel,
    },
    EmissionType.professional_travel__train__class_2.value: {
        "scope": Scope.scope3,
        "category": EmissionCategory.professional_travel,
    },
    EmissionType.professional_travel__plane__first.value: {
        "scope": Scope.scope3,
        "category": EmissionCategory.professional_travel,
    },
    EmissionType.professional_travel__plane__business.value: {
        "scope": Scope.scope3,
        "category": EmissionCategory.professional_travel,
    },
    EmissionType.professional_travel__plane__eco.value: {
        "scope": Scope.scope3,
        "category": EmissionCategory.professional_travel,
    },
    # Buildings — scope 2 except heating_thermal (scope 1)
    EmissionType.buildings__rooms__lighting.value: {
        "scope": Scope.scope2,
        "category": EmissionCategory.buildings_room,
    },
    EmissionType.buildings__rooms__cooling.value: {
        "scope": Scope.scope2,
        "category": EmissionCategory.buildings_room,
    },
    EmissionType.buildings__rooms__ventilation.value: {
        "scope": Scope.scope2,
        "category": EmissionCategory.buildings_room,
    },
    EmissionType.buildings__rooms__heating_elec.value: {
        "scope": Scope.scope2,
        "category": EmissionCategory.buildings_room,
    },
    EmissionType.buildings__rooms__heating_thermal.value: {
        "scope": Scope.scope1,
        "category": EmissionCategory.buildings_energy_combustion,
    },
    # Room-type granularity (8-digit WW items)
    EmissionType.buildings__rooms__lighting__office.value: {
        "scope": Scope.scope2,
        "category": EmissionCategory.buildings_room,
    },
    EmissionType.buildings__rooms__lighting__laboratories.value: {
        "scope": Scope.scope2,
        "category": EmissionCategory.buildings_room,
    },
    EmissionType.buildings__rooms__lighting__archives.value: {
        "scope": Scope.scope2,
        "category": EmissionCategory.buildings_room,
    },
    EmissionType.buildings__rooms__lighting__libraries.value: {
        "scope": Scope.scope2,
        "category": EmissionCategory.buildings_room,
    },
    EmissionType.buildings__rooms__lighting__auditoriums.value: {
        "scope": Scope.scope2,
        "category": EmissionCategory.buildings_room,
    },
    EmissionType.buildings__rooms__lighting__miscellaneous.value: {
        "scope": Scope.scope2,
        "category": EmissionCategory.buildings_room,
    },
    EmissionType.buildings__rooms__cooling__office.value: {
        "scope": Scope.scope2,
        "category": EmissionCategory.buildings_room,
    },
    EmissionType.buildings__rooms__cooling__laboratories.value: {
        "scope": Scope.scope2,
        "category": EmissionCategory.buildings_room,
    },
    EmissionType.buildings__rooms__cooling__archives.value: {
        "scope": Scope.scope2,
        "category": EmissionCategory.buildings_room,
    },
    EmissionType.buildings__rooms__cooling__libraries.value: {
        "scope": Scope.scope2,
        "category": EmissionCategory.buildings_room,
    },
    EmissionType.buildings__rooms__cooling__auditoriums.value: {
        "scope": Scope.scope2,
        "category": EmissionCategory.buildings_room,
    },
    EmissionType.buildings__rooms__cooling__miscellaneous.value: {
        "scope": Scope.scope2,
        "category": EmissionCategory.buildings_room,
    },
    EmissionType.buildings__rooms__ventilation__office.value: {
        "scope": Scope.scope2,
        "category": EmissionCategory.buildings_room,
    },
    EmissionType.buildings__rooms__ventilation__laboratories.value: {
        "scope": Scope.scope2,
        "category": EmissionCategory.buildings_room,
    },
    EmissionType.buildings__rooms__ventilation__archives.value: {
        "scope": Scope.scope2,
        "category": EmissionCategory.buildings_room,
    },
    EmissionType.buildings__rooms__ventilation__libraries.value: {
        "scope": Scope.scope2,
        "category": EmissionCategory.buildings_room,
    },
    EmissionType.buildings__rooms__ventilation__auditoriums.value: {
        "scope": Scope.scope2,
        "category": EmissionCategory.buildings_room,
    },
    EmissionType.buildings__rooms__ventilation__miscellaneous.value: {
        "scope": Scope.scope2,
        "category": EmissionCategory.buildings_room,
    },
    EmissionType.buildings__rooms__heating_elec__office.value: {
        "scope": Scope.scope2,
        "category": EmissionCategory.buildings_room,
    },
    EmissionType.buildings__rooms__heating_elec__laboratories.value: {
        "scope": Scope.scope2,
        "category": EmissionCategory.buildings_room,
    },
    EmissionType.buildings__rooms__heating_elec__archives.value: {
        "scope": Scope.scope2,
        "category": EmissionCategory.buildings_room,
    },
    EmissionType.buildings__rooms__heating_elec__libraries.value: {
        "scope": Scope.scope2,
        "category": EmissionCategory.buildings_room,
    },
    EmissionType.buildings__rooms__heating_elec__auditoriums.value: {
        "scope": Scope.scope2,
        "category": EmissionCategory.buildings_room,
    },
    EmissionType.buildings__rooms__heating_elec__miscellaneous.value: {
        "scope": Scope.scope2,
        "category": EmissionCategory.buildings_room,
    },
    EmissionType.buildings__rooms__heating_thermal__office.value: {
        "scope": Scope.scope1,
        "category": EmissionCategory.buildings_energy_combustion,
    },
    EmissionType.buildings__rooms__heating_thermal__laboratories.value: {
        "scope": Scope.scope1,
        "category": EmissionCategory.buildings_energy_combustion,
    },
    EmissionType.buildings__rooms__heating_thermal__archives.value: {
        "scope": Scope.scope1,
        "category": EmissionCategory.buildings_energy_combustion,
    },
    EmissionType.buildings__rooms__heating_thermal__libraries.value: {
        "scope": Scope.scope1,
        "category": EmissionCategory.buildings_energy_combustion,
    },
    EmissionType.buildings__rooms__heating_thermal__auditoriums.value: {
        "scope": Scope.scope1,
        "category": EmissionCategory.buildings_energy_combustion,
    },
    EmissionType.buildings__rooms__heating_thermal__miscellaneous.value: {
        "scope": Scope.scope1,
        "category": EmissionCategory.buildings_energy_combustion,
    },
    # Combustion fuel-type granularity
    EmissionType.buildings__combustion.value: {
        "scope": Scope.scope1,
        "category": EmissionCategory.buildings_energy_combustion,
    },
    EmissionType.buildings__combustion__natural_gas.value: {
        "scope": Scope.scope1,
        "category": EmissionCategory.buildings_energy_combustion,
    },
    EmissionType.buildings__combustion__heating_oil.value: {
        "scope": Scope.scope1,
        "category": EmissionCategory.buildings_energy_combustion,
    },
    EmissionType.buildings__combustion__biomethane.value: {
        "scope": Scope.scope1,
        "category": EmissionCategory.buildings_energy_combustion,
    },
    EmissionType.buildings__combustion__pellets.value: {
        "scope": Scope.scope1,
        "category": EmissionCategory.buildings_energy_combustion,
    },
    EmissionType.buildings__combustion__forest_chips.value: {
        "scope": Scope.scope1,
        "category": EmissionCategory.buildings_energy_combustion,
    },
    EmissionType.buildings__combustion__wood_logs.value: {
        "scope": Scope.scope1,
        "category": EmissionCategory.buildings_energy_combustion,
    },
    EmissionType.buildings__embodied_energy.value: {
        "scope": Scope.scope3,
        "category": EmissionCategory.embodied_energy,
    },
    # Process Emissions — all scope 1
    EmissionType.process_emissions__ch4.value: {
        "scope": Scope.scope1,
        "category": EmissionCategory.process_emissions,
    },
    EmissionType.process_emissions__co2.value: {
        "scope": Scope.scope1,
        "category": EmissionCategory.process_emissions,
    },
    EmissionType.process_emissions__n2o.value: {
        "scope": Scope.scope1,
        "category": EmissionCategory.process_emissions,
    },
    EmissionType.process_emissions__refrigerants.value: {
        "scope": Scope.scope1,
        "category": EmissionCategory.process_emissions,
    },
    # Equipment — all scope 2
    EmissionType.equipment__scientific.value: {
        "scope": Scope.scope2,
        "category": EmissionCategory.equipment,
    },
    EmissionType.equipment__it.value: {
        "scope": Scope.scope2,
        "category": EmissionCategory.equipment,
    },
    EmissionType.equipment__other.value: {
        "scope": Scope.scope2,
        "category": EmissionCategory.equipment,
    },
    # Purchases — scope 3 except additional (scope 1)
    EmissionType.purchases__goods_and_services.value: {
        "scope": Scope.scope3,
        "category": EmissionCategory.purchases,
    },
    EmissionType.purchases__scientific_equipment.value: {
        "scope": Scope.scope3,
        "category": EmissionCategory.purchases,
    },
    EmissionType.purchases__it_equipment.value: {
        "scope": Scope.scope3,
        "category": EmissionCategory.purchases,
    },
    EmissionType.purchases__consumable_accessories.value: {
        "scope": Scope.scope3,
        "category": EmissionCategory.purchases,
    },
    EmissionType.purchases__biological_chemical_gaseous.value: {
        "scope": Scope.scope3,
        "category": EmissionCategory.purchases,
    },
    EmissionType.purchases__services.value: {
        "scope": Scope.scope3,
        "category": EmissionCategory.purchases,
    },
    EmissionType.purchases__vehicles.value: {
        "scope": Scope.scope3,
        "category": EmissionCategory.purchases,
    },
    EmissionType.purchases__other.value: {
        "scope": Scope.scope3,
        "category": EmissionCategory.purchases,
    },
    EmissionType.purchases__additional.value: {
        "scope": Scope.scope1,
        "category": EmissionCategory.purchases,
    },
    EmissionType.purchases__additional__ln2.value: {
        "scope": Scope.scope1,
        "category": EmissionCategory.purchases,
    },
    # Research Facilities — all scope 3
    EmissionType.research_facilities__facilities.value: {
        "scope": Scope.scope3,
        "category": EmissionCategory.research_facilities,
    },
    EmissionType.research_facilities__animal.value: {
        "scope": Scope.scope3,
        "category": EmissionCategory.research_facilities,
    },
    EmissionType.research_facilities__it_facilities.value: {
        "scope": Scope.scope3,
        "category": EmissionCategory.research_facilities,
    },
    EmissionType.research_facilities__animal__mice.value: {
        "scope": Scope.scope3,
        "category": EmissionCategory.research_facilities,
    },
    EmissionType.research_facilities__animal__fish.value: {
        "scope": Scope.scope3,
        "category": EmissionCategory.research_facilities,
    },
    # External Clouds & AI — all scope 3
    EmissionType.external__clouds__virtualisation.value: {
        "scope": Scope.scope3,
        "category": EmissionCategory.external_cloud_and_ai,
    },
    EmissionType.external__clouds__calcul.value: {
        "scope": Scope.scope3,
        "category": EmissionCategory.external_cloud_and_ai,
    },
    EmissionType.external__clouds__stockage.value: {
        "scope": Scope.scope3,
        "category": EmissionCategory.external_cloud_and_ai,
    },
    EmissionType.external__ai__provider_google.value: {
        "scope": Scope.scope3,
        "category": EmissionCategory.external_cloud_and_ai,
    },
    EmissionType.external__ai__provider_mistral_ai.value: {
        "scope": Scope.scope3,
        "category": EmissionCategory.external_cloud_and_ai,
    },
    EmissionType.external__ai__provider_anthropic.value: {
        "scope": Scope.scope3,
        "category": EmissionCategory.external_cloud_and_ai,
    },
    EmissionType.external__ai__provider_openai.value: {
        "scope": Scope.scope3,
        "category": EmissionCategory.external_cloud_and_ai,
    },
    EmissionType.external__ai__provider_cohere.value: {
        "scope": Scope.scope3,
        "category": EmissionCategory.external_cloud_and_ai,
    },
    EmissionType.external__ai__provider_others.value: {
        "scope": Scope.scope3,
        "category": EmissionCategory.external_cloud_and_ai,
    },
}


# =============================================================================
# Tree traversal helpers
# =============================================================================


def get_children(root: EmissionType) -> list[EmissionType]:
    """Get direct children of a node (one level down)."""
    return [e for e in EmissionType if _PARENT_MAP.get(e.value) == root.value]


def get_subtree_leaves(root: EmissionType) -> list[int]:
    """Get all leaf emission_type_id values under a given node (recursive)."""
    kids = [e for e in EmissionType if _PARENT_MAP.get(e.value) == root.value]
    if not kids:
        return [root.value]
    result: list[int] = []
    for child in kids:
        result.extend(get_subtree_leaves(child))
    return result


def get_all_nodes(root: EmissionType) -> list[EmissionType]:
    """Get all nodes (root + intermediates + leaves) under a given node."""
    result: list[EmissionType] = [root]
    kids = [e for e in EmissionType if _PARENT_MAP.get(e.value) == root.value]
    for child in kids:
        result.extend(get_all_nodes(child))
    return result


### =============================================================================
# DataEntryEmission model
# =============================================================================


@dataclass
class FactorQuery:
    """Describes how to look up factors via classification query (Strategy B).

    Args:
        data_entry_type: Scopes the DB query to a specific data entry type.
        kind: Primary classification key (e.g. 'food', 'plane', building_name).
        subkind: Optional secondary classification key (e.g. cabin class, subcategory).
        context: Additional classification filters forwarded to the DB query
                 (e.g. ``{"category": "short_haul"}`` for flights,
                 ``{"country_code": "CH"}`` for trains).
        fallbacks: Fallback values for context keys when the exact match fails
                   (e.g. ``{"country_code": "RoW"}`` to fall back to a global factor).
    """

    data_entry_type: DataEntryTypeEnum
    kind: Optional[str] = None
    subkind: Optional[str] = None
    emission_type: Optional[EmissionType] = (
        None  # Optional, can be used for additional filtering in repo queries
    )
    context: dict = field(default_factory=dict)
    fallbacks: dict = field(default_factory=dict)


@dataclass
class EmissionComputation:
    """Describes one emitted row and how to compute its kg_co2eq.

    Exactly one of ``factor_id`` (Strategy A) or ``factor_query`` (Strategy B)
    should be set.

    For simple formulas::

        kg_co2eq = ctx[quantity_key] * factor.values[formula_key]
                   * factor.values.get(multiplier_key, multiplier_default)

    For complex formulas, set ``formula_func`` and it takes precedence over
    the key-based approach::

        kg_co2eq = formula_func(ctx, factor.values)
    """

    emission_type: EmissionType

    # --- Factor retrieval ---
    # Strategy A: direct factor ID (primary_factor_id already resolved at creation)
    factor_id: Optional[int] = None
    # Strategy B: classification query resolved at compute time
    factor_query: Optional[FactorQuery] = None

    # --- Formula (key-based, simple) ---
    # Name of the factor value key giving the emission intensity
    formula_key: str = ""
    # Name of the context key giving the physical quantity
    quantity_key: str = ""
    # Optional second multiplier from factor values (e.g. "rfi_adjustement")
    multiplier_key: Optional[str] = None
    # Value used when multiplier_key is absent from factor values
    multiplier_default: float = 1.0

    # --- Formula (callable, complex) ---
    # When set, takes precedence over key-based formula.
    # Signature: (ctx: dict, factor_values: dict) -> Optional[float]
    formula_func: Optional[Callable[[dict, dict], Optional[float]]] = None


####


class DataEntryEmissionBase(SQLModel):
    """Base data entry emission model with shared fields."""

    data_entry_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("data_entries.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        description="Reference to the source data entry",
    )
    # EmissionType value
    emission_type_id: int = Field(
        nullable=False,
        index=True,
        description="Type of emission (equipment, food, waste, commute, etc.)",
    )
    # Primary factor used for calculation (main factor for traceability)
    primary_factor_id: Optional[int] = Field(
        default=None,
        sa_column=Column(
            Integer, ForeignKey("factors.id", ondelete="CASCADE"), index=True
        ),
        description="Primary factor used for calculation (power, headcount,"
        "flight, etc.)",
    )
    # TODO: move to Decimal! (precision issues)
    kg_co2eq: float = Field(
        nullable=False,
        description="Computed emission value in kg CO2 equivalent",
    )
    additional_value: float | None = Field(
        default=None,
        sa_column=Column(
            Float,
            nullable=True,
            comment=(
                "Polymorphic physical quantity tied to this emission row. "
                "Unit is inferred from emission_type_id "
                "(e.g. km for commuting and travel, kg for food and waste)."
            ),
        ),
        description=(
            "Polymorphic physical quantity tied to this emission row. "
            "Unit is inferred from emission_type_id "
            "(e.g. km for commuting and travel, kg for food and waste)."
        ),
    )
    scope: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, nullable=True),
        description="Scope (1/2/3) for leaf rows; NULL for rollup rows",
    )
    meta: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON),
        description="Calculation inputs and factors_used array for full traceability",
    )
    computed_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(TIMESTAMP(timezone=True), nullable=False, index=True),
        description="Timestamp when emission was computed",
    )


class DataEntryEmission(DataEntryEmissionBase, table=True):
    """
    Generic emission results table.

    Stores computed CO2 emissions for all module types. Supports:
    - Multiple emissions per data entry (headcount → food, waste, commute)
    - Single emission per data entry (equipment → equipment)
    - Multi-factor calculations (all factors stored in meta.factors_used)

    One data entry can produce N emission rows, one per emission_type.

    Factor storage:
    - primary_factor_id: Main calculation factor
        (for traceability and recalculation queries)
    - meta.factors_used: Array of all factors with roles
        [{id, role, factor_family, values}]

    For equipment calculations (2 factors):
    - primary_factor_id → power factor (watts)
    - meta.factors_used → [{role: 'primary', ...power},
        {role: 'emission'}]
    - Formula: kg_co2eq = annual_kwh x emission_factor.values.kg_co2eq_per_kwh

    For headcount calculations (1 factor per emission):
    - primary_factor_id → headcount factor for that emission_type
    - meta.factors_used → [{role: 'primary', ...headcount_factor}]
    - Formula: kg_co2eq = fte x factor.values.kg_co2eq_per_fte

    Category/treemaps: Use emission_type.path or emission_type.parent
    to derive categories (e.g., "professional_travel__planes__eco"
    ->  "Professional Travel")

    Versioning: All changes tracked via document_versions table.
    The row is always updated in place; history is in document_versions.

    Examples:
        Equipment emission (1 row):
            data_entry_id=42, emission_type_id=80100 (equipment__scientific),
            kg_co2eq=123.4, primary_factor_id=5 (power),
            meta={
                "annual_kwh": 3569.3,
                "factors_used": [
                    {"id": 5, "role": "primary",
                        "factor_family": "power", "values": {...}},
                    {"id": 10, "role": "emission",
                        "factor_family": "emission", "values": {...}}
                ]
            }

        Headcount emissions (4 rows):
            data_entry_id=77, emission_type_id=10000 (food), kg_co2eq=336.0,
            primary_factor_id=11 (food factor),
            meta={
                "fte": 0.8,
                "factors_used": [{"id": 11, "role": "primary", "values": {...}}]
            }
    """

    __tablename__ = "data_entry_emissions"

    id: Optional[int] = Field(default=None, primary_key=True, index=True)

    def __repr__(self) -> str:
        return (
            f"<DataEntryEmission data_entry={self.data_entry_id} "
            f"type={self.emission_type_id}: {self.kg_co2eq} kgCO2eq>"
        )
