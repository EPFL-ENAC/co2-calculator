"""Tests for HeadcountMembersApiProvider.

Covers transform_data mapping (captions parametrized as class constants so
the test pins the mapping, not the datasource), unit-prefix stripping edge
cases, skip-row rules, and factory registration.
"""

from unittest.mock import AsyncMock

import pytest

from app.models.data_ingestion import EntityType, IngestionMethod, TargetType
from app.models.module_type import ModuleTypeEnum
from app.services.data_ingestion.api_providers.headcount_members_api_provider import (
    HeadcountMembersApiProvider,
)
from app.services.data_ingestion.provider_factory import ProviderFactory


def _make_provider(**config_overrides):
    """Build a HeadcountMembersApiProvider without touching the DB.

    Credentials come from the DB via ``_ensure_credentials``; transform tests
    never hit the network or DB, so a mock session is enough.
    """
    config = {"year": 2025, "module_type_id": 1, **config_overrides}
    return HeadcountMembersApiProvider(
        config,
        None,
        job_session=None,
        data_session=AsyncMock(),
    )


def _make_record(**overrides):
    record = {
        HeadcountMembersApiProvider.CAPTION_NAME: "Role Std",
        HeadcountMembersApiProvider.CAPTION_SCIPER: "123456",
        HeadcountMembersApiProvider.CAPTION_SIUS: "51",
        HeadcountMembersApiProvider.CAPTION_FTE: "0.5",
        HeadcountMembersApiProvider.CAPTION_UNIT: "F0828",
    }
    record.update(overrides)
    return record


# ---------------------------------------------------------------------------
# transform_data — field mapping
# ---------------------------------------------------------------------------


class TestTransformData:
    async def test_transform_maps_member_fields(self):
        provider = _make_provider()
        out = await provider.transform_data([_make_record()])
        assert len(out) == 1
        assert out[0]["user_institutional_id"] == "123456"
        assert out[0]["fte"] == 0.5
        assert out[0]["sius_code"] == "51"
        assert out[0]["name"] == "Role Std"
        assert out[0]["note"] is None
        assert out[0]["unit_institutional_id"] == "0828"  # prefix stripped

    async def test_sciper_coerced_to_string(self):
        provider = _make_provider()
        out = await provider.transform_data(
            [_make_record(**{HeadcountMembersApiProvider.CAPTION_SCIPER: 123456})]
        )
        assert out[0]["user_institutional_id"] == "123456"

    async def test_missing_name_defaults_to_empty_string(self):
        provider = _make_provider()
        out = await provider.transform_data(
            [_make_record(**{HeadcountMembersApiProvider.CAPTION_NAME: None})]
        )
        assert out[0]["name"] == ""

    async def test_sius_coerced_to_string(self):
        provider = _make_provider()
        out = await provider.transform_data(
            [_make_record(**{HeadcountMembersApiProvider.CAPTION_SIUS: 51})]
        )
        assert out[0]["sius_code"] == "51"


# ---------------------------------------------------------------------------
# transform_data — skip-row rules
# ---------------------------------------------------------------------------


class TestTransformSkipRules:
    @pytest.mark.parametrize("sciper", [None, "", "   "])
    async def test_skips_missing_sciper(self, sciper):
        provider = _make_provider()
        out = await provider.transform_data(
            [_make_record(**{HeadcountMembersApiProvider.CAPTION_SCIPER: sciper})]
        )
        assert out == []

    @pytest.mark.parametrize("fte", [None, "", "abc", "1,2"])
    async def test_skips_unparseable_fte(self, fte):
        provider = _make_provider()
        out = await provider.transform_data(
            [_make_record(**{HeadcountMembersApiProvider.CAPTION_FTE: fte})]
        )
        assert out == []

    async def test_fte_zero_is_kept(self):
        # 0.0 is a valid FTE (e.g. hosted guests) — must not be dropped
        # by a falsy check.
        provider = _make_provider()
        out = await provider.transform_data(
            [_make_record(**{HeadcountMembersApiProvider.CAPTION_FTE: "0"})]
        )
        assert len(out) == 1
        assert out[0]["fte"] == 0.0

    async def test_mixed_batch_keeps_only_valid_rows(self):
        provider = _make_provider()
        out = await provider.transform_data(
            [
                _make_record(),
                _make_record(**{HeadcountMembersApiProvider.CAPTION_SCIPER: ""}),
                _make_record(**{HeadcountMembersApiProvider.CAPTION_FTE: "x"}),
            ]
        )
        assert len(out) == 1


# ---------------------------------------------------------------------------
# _strip_unit_prefix — edge cases
# ---------------------------------------------------------------------------


class TestStripUnitPrefix:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("F0828", "0828"),  # letter prefix + digits: stripped
            ("1234", "1234"),  # all digits: unchanged
            ("FA828", "FA828"),  # two letters: unchanged
            ("F", "F"),  # single char: unchanged
            ("", ""),  # empty: unchanged
            (None, None),  # missing: passed through
        ],
    )
    def test_strip_unit_prefix(self, raw, expected):
        assert HeadcountMembersApiProvider._strip_unit_prefix(raw) == expected

    async def test_transform_preserves_none_unit(self):
        # A null unit must stay None so the fail-fast guard in
        # _resolve_carbon_report_modules fires — no sentinel values.
        provider = _make_provider()
        out = await provider.transform_data(
            [_make_record(**{HeadcountMembersApiProvider.CAPTION_UNIT: None})]
        )
        assert out[0]["unit_institutional_id"] is None

    async def test_resolve_modules_error_uses_headcount_noun(self):
        # The shared resolver's user-facing wording is parametrized on
        # INGEST_NOUN, so headcount imports must not surface travel jargon.
        provider = _make_provider(year=None)
        with pytest.raises(ValueError, match="year is required for headcount"):
            await provider._resolve_carbon_report_modules([])


# ---------------------------------------------------------------------------
# _build_data_entry — persisted payload shape
# ---------------------------------------------------------------------------


class TestBuildDataEntry:
    def test_member_entry_payload_keys(self):
        provider = _make_provider()
        record = {
            "unit_institutional_id": "0828",
            "user_institutional_id": "123456",
            "name": "Role Std",
            "sius_code": "51",
            "fte": 0.5,
            "note": None,
            "carbon_report_module_id": 42,
        }
        entry = provider._build_data_entry(record, 42)
        assert entry.carbon_report_module_id == 42
        assert entry.data_entry_type_id == 1  # DataEntryTypeEnum.member
        # Exactly the member data keys (matches HeadCountCreate) — routing
        # fields like unit_institutional_id must not leak into the JSON.
        assert entry.data == {
            "name": "Role Std",
            "sius_code": "51",
            "user_institutional_id": "123456",
            "fte": 0.5,
            "note": None,
        }


# ---------------------------------------------------------------------------
# ingest — orchestration
# ---------------------------------------------------------------------------


class TestIngest:
    async def test_ingest_injects_module_ids_and_loads(self):
        provider = _make_provider()
        provider.fetch_data = AsyncMock(
            return_value=[
                _make_record(),
                _make_record(
                    **{
                        HeadcountMembersApiProvider.CAPTION_SCIPER: "654321",
                        HeadcountMembersApiProvider.CAPTION_UNIT: "F9999",
                    }
                ),
            ]
        )
        provider._resolve_carbon_report_modules = AsyncMock(return_value={"0828": 42})
        provider._load_data = AsyncMock(return_value={"inserted": 1})
        provider._update_job = AsyncMock()

        result = await provider.ingest()

        loaded = provider._load_data.await_args.args[0]
        assert len(loaded) == 1
        assert loaded[0]["carbon_report_module_id"] == 42
        stats = result["stats"]
        assert stats["rows_processed"] == 1
        assert stats["rows_skipped"] == 1  # unit 9999 has no module
        assert result["inserted"] == 1

    async def test_ingest_fails_when_no_valid_records(self):
        provider = _make_provider()
        provider.fetch_data = AsyncMock(return_value=[_make_record()])
        provider._resolve_carbon_report_modules = AsyncMock(return_value={})
        provider._load_data = AsyncMock()
        provider._update_job = AsyncMock()

        with pytest.raises(ValueError, match="No valid records"):
            await provider.ingest()
        provider._load_data.assert_not_awaited()


# ---------------------------------------------------------------------------
# Factory registration
# ---------------------------------------------------------------------------


class TestFactoryRegistration:
    def test_factory_resolves_headcount_api_provider(self):
        provider_class = ProviderFactory.get_provider_by_keys(
            ModuleTypeEnum.headcount,
            IngestionMethod.api,
            TargetType.DATA_ENTRIES,
            EntityType.MODULE_PER_YEAR,
        )
        assert provider_class is HeadcountMembersApiProvider
