from typing import Optional

from app.models.data_ingestion import IngestionMethod, TargetType
from app.models.module_type import ModuleTypeEnum
from app.models.user import User
from app.services.data_ingestion.base_provider import DataIngestionProvider
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
    PROVIDERS = {
        # Data Entries providers
        # ("travel", "tableau_api", "data_entries"): ProfessionalTravelApiProvider,
        (
            ModuleTypeEnum.professional_travel,
            IngestionMethod.api,
            TargetType.DATA_ENTRIES,
        ): ProfessionalTravelApiProvider,
        # ("travel", "csv_upload", "data_entries"): CSVDataEntriesProvider,
        # ("headcount", "csv_upload", "data_entries"): CSVDataEntriesProvider,
        # ("purchases", "csv_upload", "data_entries"): CSVDataEntriesProvider,
        # # Factors providers
        # ("travel", "csv_upload", "factors"): CSVFactorsProvider,
        # ("headcount", "csv_upload", "factors"): CSVFactorsProvider,
    }

    PROVIDERS_BY_CLASS_NAME = {v.__name__: v for _, v in PROVIDERS.items()}

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
    ) -> Optional[type[DataIngestionProvider]]:
        """
        Get the appropriate provider class.
        """
        return ProviderFactory.PROVIDERS.get(
            (module_type_id, ingestion_method, target_type)
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
        key = (module_type_id, ingestion_method, target_type)

        provider_class = cls.PROVIDERS.get(key)
        if not provider_class:
            return None

        return provider_class(
            config=config or {},
            user=user,
        )
