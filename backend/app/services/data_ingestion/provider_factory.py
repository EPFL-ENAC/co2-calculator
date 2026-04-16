from typing import Optional

from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.data_entry import DataEntryTypeEnum
from app.models.data_ingestion import EntityType, IngestionMethod, TargetType
from app.models.module_type import ModuleTypeEnum
from app.models.user import User
from app.services.data_ingestion.api_providers.professional_travel_api_provider import (
    ProfessionalTravelApiProvider,
)
from app.services.data_ingestion.base_provider import DataIngestionProvider
from app.services.data_ingestion.computed_providers.research_facilities_animal import (
    ResearchFacilitiesAnimalFactorUpdateProvider,
)
from app.services.data_ingestion.computed_providers.research_facilities_common import (
    ResearchFacilitiesCommonFactorUpdateProvider,
)
from app.services.data_ingestion.csv_providers import (
    ModulePerYearCSVProvider,
    ModulePerYearFactorCSVProvider,
    ModulePerYearReductionObjectivesApiProvider,
    ModulePerYearReferenceDataApiProvider,
    ModuleUnitSpecificCSVProvider,
)


class ProviderFactory:
    """Factory to create the right provider based on module + provider
    type + entity type"""

    # Registry of CSV/API providers.
    # Key: (module_type, ingestion_method, target_type, entity_type)
    PROVIDERS: dict[
        tuple[ModuleTypeEnum | None, IngestionMethod, TargetType, EntityType],
        type[DataIngestionProvider],
    ] = {
        # MODULE_UNIT_SPECIFIC CSV Providers
        **{
            (
                module_type,
                IngestionMethod.csv,
                TargetType.DATA_ENTRIES,
                EntityType.MODULE_UNIT_SPECIFIC,
            ): ModuleUnitSpecificCSVProvider
            for module_type in ModuleTypeEnum
        },
        # MODULE_PER_YEAR CSV Providers
        **{
            (
                module_type,
                IngestionMethod.csv,
                TargetType.DATA_ENTRIES,
                EntityType.MODULE_PER_YEAR,
            ): ModulePerYearCSVProvider
            for module_type in ModuleTypeEnum
        },
        # MODULE_PER_YEAR factor CSV Providers
        **{
            (
                module_type,
                IngestionMethod.csv,
                TargetType.FACTORS,
                EntityType.MODULE_PER_YEAR,
            ): ModulePerYearFactorCSVProvider
            for module_type in ModuleTypeEnum
        },
        ## MODULE_PER_YEAR REDUCTION OBJECTIVES
        (
            None,
            IngestionMethod.csv,
            TargetType.REDUCTION_OBJECTIVES,
            EntityType.MODULE_PER_YEAR,
        ): ModulePerYearReductionObjectivesApiProvider,
        ## MODULE_PER_YEAR REFERENCE DATA
        (
            None,
            IngestionMethod.csv,
            TargetType.REFERENCE_DATA,
            EntityType.MODULE_PER_YEAR,
        ): ModulePerYearReferenceDataApiProvider,
        # API Providers
        (
            ModuleTypeEnum.professional_travel,
            IngestionMethod.api,
            TargetType.DATA_ENTRIES,
            EntityType.MODULE_PER_YEAR,
        ): ProfessionalTravelApiProvider,
    }

    # WHAT IS THAT?
    # Registry of computed providers that are keyed by data_entry_type as well.
    # Key: (module_type, data_entry_type, ingestion_method, target_type, entity_type)
    COMPUTED_FACTOR_PROVIDERS: dict[
        tuple[
            ModuleTypeEnum,
            DataEntryTypeEnum,
            IngestionMethod,
            TargetType,
            EntityType,
        ],
        type[DataIngestionProvider],
    ] = {
        (
            ModuleTypeEnum.research_facilities,
            DataEntryTypeEnum.mice_and_fish_animal_facilities,
            IngestionMethod.computed,
            TargetType.FACTORS,
            EntityType.MODULE_PER_YEAR,
        ): ResearchFacilitiesAnimalFactorUpdateProvider,
        (
            ModuleTypeEnum.research_facilities,
            DataEntryTypeEnum.research_facilities,
            IngestionMethod.computed,
            TargetType.FACTORS,
            EntityType.MODULE_PER_YEAR,
        ): ResearchFacilitiesCommonFactorUpdateProvider,
    }

    PROVIDERS_BY_CLASS_NAME: dict[str, type[DataIngestionProvider]] = {
        **{v.__name__: v for _, v in PROVIDERS.items()},
        **{v.__name__: v for _, v in COMPUTED_FACTOR_PROVIDERS.items()},
    }

    @staticmethod
    def get_provider_class(
        provider_class_name: str,
    ) -> Optional[type[DataIngestionProvider]]:
        """
        Get the appropriate provider class.
        """
        return ProviderFactory.PROVIDERS_BY_CLASS_NAME.get(provider_class_name)

    @staticmethod
    def get_provider_by_keys(
        module_type_id: Optional[ModuleTypeEnum],
        ingestion_method: IngestionMethod,
        target_type: TargetType,
        entity_type: EntityType,
        data_entry_type_id: DataEntryTypeEnum | int | None = None,
    ) -> Optional[type[DataIngestionProvider]]:
        """
        Get the appropriate provider class by routing keys.

        For computed providers, a 5-tuple lookup using data_entry_type is
        attempted first; falls back to the 4-tuple PROVIDERS dict for CSV/API
        providers that don't carry a data_entry_type in their key.
        """
        if data_entry_type_id is not None:
            try:
                det = DataEntryTypeEnum(data_entry_type_id)
            except ValueError:
                det = None
            if module_type_id is None:
                raise ValueError("module_type_id is required for computed providers")
            if det is not None:
                five_tuple_key = (
                    module_type_id,
                    det,
                    ingestion_method,
                    target_type,
                    entity_type,
                )
                result = ProviderFactory.COMPUTED_FACTOR_PROVIDERS.get(five_tuple_key)
                if result is not None:
                    return result
        return ProviderFactory.PROVIDERS.get(
            (module_type_id, ingestion_method, target_type, entity_type)
        )

    @classmethod
    async def create_provider(
        cls,
        ingestion_method: IngestionMethod,
        target_type: TargetType,
        config: dict,
        user: User,
        job_session: Optional[AsyncSession] = None,
        data_session: Optional[AsyncSession] = None,
    ) -> Optional[DataIngestionProvider]:
        """
        Create the appropriate provider instance.

        Determines entity_type from config (carbon_report_module_id presence)
        and uses it to select the correct provider class.
        """
        # Safely extract and validate entity_type from config
        entity_type_value = config.get("entity_type")
        if not entity_type_value:
            return None

        try:
            entity_type = EntityType(entity_type_value)
        except (ValueError, KeyError):
            # Invalid entity_type value - return None to signal configuration error
            return None

        data_entry_type_id = config.get("data_entry_type_id")
        module_type_id = config.get("module_type_id")
        # if module_type_id is None:
        #     return None
        provider_class = cls.get_provider_by_keys(
            module_type_id=module_type_id,
            ingestion_method=ingestion_method,
            target_type=target_type,
            entity_type=entity_type,
            data_entry_type_id=data_entry_type_id,
        )

        if not provider_class:
            return None
        if data_session is None:
            raise ValueError("Data session is required to create provider instance")
        return provider_class(
            config=config, user=user, job_session=job_session, data_session=data_session
        )
