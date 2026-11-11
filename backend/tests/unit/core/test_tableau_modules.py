"""TABLEAU_MODULES turns the Tableau import on per module (#500)."""

import pytest

from app.core.config import get_settings
from app.models.data_ingestion import EntityType, IngestionMethod, TargetType
from app.models.module_type import ModuleTypeEnum
from app.services.data_ingestion.provider_factory import ProviderFactory


def _api_provider(module: ModuleTypeEnum):
    return ProviderFactory.get_provider_by_keys(
        module, IngestionMethod.api, TargetType.DATA_ENTRIES, EntityType.MODULE_PER_YEAR
    )


def test_empty_list_turns_tableau_off(monkeypatch):
    monkeypatch.setattr(get_settings(), "TABLEAU_MODULES", "")

    assert ProviderFactory.tableau_modules() == frozenset()
    assert _api_provider(ModuleTypeEnum.headcount) is None


def test_listed_module_keeps_its_import_and_the_others_lose_it(monkeypatch):
    monkeypatch.setattr(get_settings(), "TABLEAU_MODULES", " headcount ")

    assert ProviderFactory.tableau_modules() == {ModuleTypeEnum.headcount}
    assert _api_provider(ModuleTypeEnum.headcount) is not None
    assert _api_provider(ModuleTypeEnum.professional_travel) is None


def test_the_csv_upload_does_not_depend_on_the_list(monkeypatch):
    monkeypatch.setattr(get_settings(), "TABLEAU_MODULES", "")

    provider = ProviderFactory.get_provider_by_keys(
        ModuleTypeEnum.headcount,
        IngestionMethod.csv,
        TargetType.DATA_ENTRIES,
        EntityType.MODULE_PER_YEAR,
    )
    assert provider is not None


@pytest.mark.parametrize("value", ["headcont", "buildings"])
def test_a_wrong_module_stops_the_startup(monkeypatch, value):
    """A typo, or a module without a Tableau provider, raises at boot."""
    monkeypatch.setattr(get_settings(), "TABLEAU_MODULES", value)

    with pytest.raises(ValueError, match="TABLEAU_MODULES"):
        ProviderFactory.tableau_modules()
