from typing import Optional, cast

from app.models.data_entry import DataEntryTypeEnum
from app.models.data_ingestion import IngestionMethod, TargetType
from app.models.module_type import ModuleTypeEnum
from app.models.user import User
from app.services.data_ingestion.base_provider import DataIngestionProvider
from app.services.data_ingestion.data_entries_csv_provider import (
    DataEntriesCSVProvider,
)
from app.services.data_ingestion.professional_travel_api_provider import (
    ProfessionalTravelApiProvider,
)

# from app.services.data_ingestion.csv_provider import (
#     CSVDataEntriesProvider,
#     CSVFactorsProvider,
# )


class ProviderFactory:
    """Factory to create the right provider based on module + provider type"""

    # Registry of available providers
    # TODO: use data_entry_type_id when we have factors providers!!
    PROVIDERS: dict[
        tuple[ModuleTypeEnum, IngestionMethod, TargetType, None],
        type[DataIngestionProvider],
    ] = {
        # Data Entries providers
        # ("travel", "tableau_api", "data_entries"): ProfessionalTravelApiProvider,
        **{
            (
                module_type,
                IngestionMethod.csv,
                TargetType.DATA_ENTRIES,
                None,
            ): DataEntriesCSVProvider
            for module_type in ModuleTypeEnum
        },
        (
            ModuleTypeEnum.professional_travel,
            IngestionMethod.api,
            TargetType.DATA_ENTRIES,
            None,
        ): ProfessionalTravelApiProvider,
        # ("travel", "csv_upload", "data_entries"): CSVDataEntriesProvider,
        # ("headcount", "csv_upload", "data_entries"): CSVDataEntriesProvider,
        # ("purchases", "csv_upload", "data_entries"): CSVDataEntriesProvider,
        # # Factors providers
        # ("travel", "csv_upload", "factors"): CSVFactorsProvider,
        # ("headcount", "csv_upload", "factors"): CSVFactorsProvider,
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
        data_entry_type_id: DataEntryTypeEnum | int | None = None,
    ) -> Optional[type[DataIngestionProvider]]:
        """
        Get the appropriate provider class.
        """
        # Try to get provider with specific data_entry_type_id first,
        # then fall back to None
        provider = ProviderFactory.PROVIDERS.get(
            cast(
                tuple[ModuleTypeEnum, IngestionMethod, TargetType, None],
                (module_type_id, ingestion_method, target_type, data_entry_type_id),
            )
        )
        if provider:
            return provider
        return ProviderFactory.PROVIDERS.get(
            (module_type_id, ingestion_method, target_type, None)
        )

    @classmethod
    async def create_provider(
        cls,
        module_type_id: ModuleTypeEnum,
        ingestion_method: IngestionMethod,
        target_type: TargetType,
        config: dict,
        user: User,
    ) -> Optional[DataIngestionProvider]:
        """
        Create the appropriate provider instance.
        """
        data_entry_type_id = config.get("data_entry_type_id") if config else None

        # Try to get provider with specific data_entry_type_id first,
        # then fall back to None
        provider_class = cls.PROVIDERS.get(
            cast(
                tuple[ModuleTypeEnum, IngestionMethod, TargetType, None],
                (module_type_id, ingestion_method, target_type, data_entry_type_id),
            )
        )
        if not provider_class:
            provider_class = cls.PROVIDERS.get(
                (module_type_id, ingestion_method, target_type, None)
            )
        if not provider_class:
            return None

        return provider_class(
            config=config or {},
            user=user,
        )
