"""Seed script to generate random factors for all data entry types."""

import asyncio
import random

from faker import Faker
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db import SessionLocal
from app.models.data_entry import DataEntryTypeEnum
from app.models.data_entry_emission import EmissionTypeEnum
from app.models.factor import Factor

fake = Faker()


async def create_factors(session: AsyncSession):
    """Create random factors for all data entry types and emission types."""
    factors = []

    # Create conversion factors (energy mix factors)
    regions = ["CH", "EU", "US", "CN", "IN"]
    for region in regions:
        factor = Factor(
            emission_type_id=EmissionTypeEnum.energy,
            is_conversion=True,
            data_entry_type_id=DataEntryTypeEnum.energy_mix,
            classification={
                "region": region,
                "source": f"Energy mix data for {region}",
                "unit": "kgCO2eq/kWh",
                "description": f"Electricity consumption mix for {region}",
                "methodology": "Life cycle analysis",
            },
            values={
                "kg_co2eq_per_kwh": round(random.uniform(0.05, 0.5), 6),  # nosec B311
            },
        )
        factors.append(factor)

    # Create equipment factors
    equipment_classes = [
        "Computers",
        "Servers",
        "Laboratory Equipment",
        "Office Equipment",
        "Manufacturing Equipment",
        "Medical Devices",
        "Telecommunications",
        "Lighting Systems",
        "HVAC Systems",
        "Kitchen Appliances",
    ]

    sub_classes = [
        "High Efficiency",
        "Standard",
        "Low Efficiency",
        "Industrial Grade",
        "Consumer Grade",
        "Professional Grade",
    ]

    for equipment_class in equipment_classes:
        for data_entry_type in [
            DataEntryTypeEnum.scientific,
            DataEntryTypeEnum.it,
            DataEntryTypeEnum.other,
        ]:
            for _ in range(
                random.randint(2, 5)  # nosec B311
            ):  # Create 2-5 variants of each
                sub_class = (
                    fake.random_element(elements=sub_classes)
                    if fake.boolean(chance_of_getting_true=70)
                    else None
                )

                factor = Factor(
                    emission_type_id=EmissionTypeEnum.equipment,
                    is_conversion=False,
                    data_entry_type_id=data_entry_type,
                    classification={
                        "class": equipment_class,
                        "kind": equipment_class,
                        "sub_class": sub_class,
                        "subkind": sub_class,
                        "unit": "W",
                        "description": f"Power factor for {equipment_class}"
                        + (f" - {sub_class}" if sub_class else ""),
                    },
                    values={
                        "active_power_w": round(random.uniform(50, 5000), 2),  # nosec B311
                        "standby_power_w": round(random.uniform(0, 50), 2),  # nosec B311
                    },
                )
                factors.append(factor)

    # Create headcount factors (food, waste, transport, grey_energy)
    headcount_types = [
        (EmissionTypeEnum.food, "kg_co2eq_per_fte", "Food consumption"),
        (EmissionTypeEnum.waste, "kg_co2eq_per_fte", "Waste generation"),
        (EmissionTypeEnum.commuting, "kg_co2eq_per_fte", "Commuting emissions"),
        (EmissionTypeEnum.grey_energy, "kg_co2eq_per_fte", "Grey energy consumption"),
    ]

    for emission_type, value_key, description in headcount_types:
        for data_entry_type in [DataEntryTypeEnum.member, DataEntryTypeEnum.student]:
            factor = Factor(
                emission_type_id=emission_type,
                is_conversion=False,
                data_entry_type_id=data_entry_type,
                classification={
                    "description": description,
                    "unit": "kgCO2eq/FTE",
                },
                values={
                    value_key: round(random.uniform(100, 1000), 2),  # nosec B311
                },
            )
            factors.append(factor)

    # Create travel factors
    # Plane factors
    cabin_classes = ["economy", "business", "first"]
    distance_bands = [
        ("Short-haul", 0, 1000),
        ("Medium-haul", 1000, 3000),
        ("Long-haul", 3000, 10000),
    ]

    for cabin_class in cabin_classes:
        for band_name, min_dist, max_dist in distance_bands:
            factor = Factor(
                emission_type_id=EmissionTypeEnum.plane,
                is_conversion=False,
                data_entry_type_id=DataEntryTypeEnum.plane,
                classification={
                    "cabin_class": cabin_class,
                    "distance_band": band_name,
                    "min_distance": min_dist,
                    "max_distance": max_dist,
                    "description": f"Plane travel factor for {cabin_class} "
                    f"class on {band_name} flights",
                },
                values={
                    "kg_co2eq_per_km": round(random.uniform(0.1, 0.5), 4),  # nosec B311
                    "radiative_forcing_factor": round(random.uniform(1.0, 2.0), 2),  # nosec B311
                },
            )
            factors.append(factor)

    # Train factors
    countries = ["CH", "DE", "FR", "IT", "AT", "NL", "BE", "UK", "ES", "PT"]
    for country in countries:
        factor = Factor(
            emission_type_id=EmissionTypeEnum.train,
            is_conversion=False,
            data_entry_type_id=DataEntryTypeEnum.train,
            classification={
                "country": country,
                "description": f"Train travel factor for {country}",
            },
            values={
                "kg_co2eq_per_km": round(random.uniform(0.01, 0.1), 4),  # nosec B311
            },
        )
        factors.append(factor)

    # Create external cloud factors
    cloud_providers = ["AWS", "Azure", "Google Cloud", "IBM Cloud", "Oracle Cloud"]
    service_types = ["storage", "compute", "database", "networking", "analytics"]

    for provider in cloud_providers:
        for service in service_types:
            factor = Factor(
                emission_type_id=random.choice(  # nosec B311
                    [
                        EmissionTypeEnum.stockage,
                        EmissionTypeEnum.calcul,
                        EmissionTypeEnum.virtualisation,
                    ]
                ),
                is_conversion=False,
                data_entry_type_id=DataEntryTypeEnum.external_clouds,
                classification={
                    "cloud_provider": provider,
                    "service_type": service,
                    "kind": provider,
                    "subkind": service,
                    "description": f"Cloud factor for {provider} {service}",
                },
                values={
                    "kg_co2eq_per_dollar": round(random.uniform(0.1, 1.0), 4),  # nosec B311
                },
            )
            factors.append(factor)

    # Create external AI factors
    ai_providers = [
        "OpenAI",
        "Anthropic",
        "Google AI",
        "Microsoft Azure AI",
        "Amazon AI",
    ]
    ai_uses = [
        "text_generation",
        "image_generation",
        "code_generation",
        "voice_processing",
        "video_analysis",
    ]

    for provider in ai_providers:
        for use in ai_uses:
            factor = Factor(
                emission_type_id=EmissionTypeEnum.ai_provider,
                is_conversion=False,
                data_entry_type_id=DataEntryTypeEnum.external_ai,
                classification={
                    "ai_provider": provider,
                    "ai_use": use,
                    "kind": provider,
                    "subkind": use,
                    "description": f"AI factor for {provider} {use}",
                },
                values={
                    "g_co2eq_per_request": round(random.uniform(0.1, 10.0), 2),  # nosec B311
                },
            )
            factors.append(factor)

    # Create process emissions factors
    gas_types = [
        ("CO2", "Carbon Dioxide"),
        ("CH4", "Methane"),
        ("N2O", "Nitrous Oxide"),
        ("HFC", "Hydrofluorocarbons"),
        ("PFC", "Perfluorocarbons"),
        ("SF6", "Sulfur Hexafluoride"),
        ("NF3", "Nitrogen Trifluoride"),
    ]

    industries = [
        "Chemical",
        "Steel",
        "Cement",
        "Paper",
        "Glass",
        "Aluminum",
        "Oil & Gas",
    ]

    for gas_code, gas_name in gas_types:
        for industry in industries:
            factor = Factor(
                emission_type_id=EmissionTypeEnum.process_emissions,
                is_conversion=False,
                data_entry_type_id=DataEntryTypeEnum.process_emissions,
                classification={
                    "gas_type": gas_code,
                    "gas_name": gas_name,
                    "industry": industry,
                    "description": f"Process emissions factor for"
                    f"{gas_name} in {industry} industry",
                },
                values={
                    "gwp_kg_co2eq_per_kg": round(random.uniform(1, 10000), 2),  # nosec B311
                },
            )
            factors.append(factor)

    # Bulk insert factors
    session.add_all(factors)
    await session.commit()

    # Refresh to get IDs
    for factor in factors:
        await session.refresh(factor)

    print(f"Created {len(factors)} factors.")
    return factors


async def main():
    async with SessionLocal() as session:
        # Generate factors
        factors = await create_factors(session)

        print(f"Created {len(factors)} factors.")


if __name__ == "__main__":
    asyncio.run(main())
