from typing import Optional

from app.models.data_entry import DataEntryTypeEnum
from app.models.data_ingestion import EntityType, IngestionMethod, TargetType
from app.models.module_type import ModuleTypeEnum
from app.models.user import User
from app.services.data_ingestion.base_provider import DataIngestionProvider
from app.services.data_ingestion.csv_providers import (
    ModulePerYearCSVProvider,
    ModuleUnitSpecificCSVProvider,
)
from app.services.data_ingestion.professional_travel_api_provider import (
    ProfessionalTravelApiProvider,
)


class ProviderFactory:
    """Factory to create the right provider based on module + provider
    type + entity type"""

    # Registry of available providers
    # Key: (module_type, ingestion_method, target_type, entity_type)
    PROVIDERS: dict[
        tuple[ModuleTypeEnum, IngestionMethod, TargetType, EntityType],
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
        # API Providers
        (
            ModuleTypeEnum.professional_travel,
            IngestionMethod.api,
            TargetType.DATA_ENTRIES,
            EntityType.MODULE_PER_YEAR,
        ): ProfessionalTravelApiProvider,
    }

    PROVIDERS_BY_CLASS_NAME: dict[str, type[DataIngestionProvider]] = {
        v.__name__: v for _, v in PROVIDERS.items()
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
        module_type_id: ModuleTypeEnum,
        ingestion_method: IngestionMethod,
        target_type: TargetType,
        entity_type: EntityType,
        data_entry_type_id: DataEntryTypeEnum | int | None = None,
    ) -> Optional[type[DataIngestionProvider]]:
        """
        Get the appropriate provider class by routing keys.

        entity_type determines which provider variant to use
        (e.g., MODULE_UNIT_SPECIFIC vs MODULE_PER_YEAR).
        """
        return ProviderFactory.PROVIDERS.get(
            (module_type_id, ingestion_method, target_type, entity_type)
        )

    @classmethod
    async def create_provider(
        cls,
        module_type_id: ModuleTypeEnum,
        ingestion_method: IngestionMethod,
        target_type: TargetType,
        config: dict,
        user: User,
        job_session=None,
        data_session=None,
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

        # Fetch the provider class using the entity_type directly from config
        provider_class = cls.PROVIDERS.get(
            (
                module_type_id,
                ingestion_method,
                target_type,
                entity_type,
            )
        )

        if not provider_class:
            return None
        return provider_class(
            config=config, user=user, job_session=job_session, data_session=data_session
        )
