"""Tests for year_configuration.py pure helper functions."""

from types import SimpleNamespace

from app.api.v1.year_configuration import (
    _build_job_lookup,
    _build_jobs_list,
    _deep_merge,
    _enrich_config_with_jobs,
    generate_unique_filename,
    get_files_storage_path,
)

# ---------------------------------------------------------------------------
# Helpers — fake job objects
# ---------------------------------------------------------------------------


def _fake_job(**overrides):
    defaults = dict(
        id=1,
        module_type_id=2,
        data_entry_type_id=20,
        year=2024,
        ingestion_method=SimpleNamespace(value=0),
        target_type=SimpleNamespace(value=0),
        state=SimpleNamespace(value=3),
        result=SimpleNamespace(value=0),
        status_message="OK",
        meta={"rows": 10},
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# ---------------------------------------------------------------------------
# _build_job_lookup
# ---------------------------------------------------------------------------
class TestBuildJobLookup:
    def test_builds_lookup(self):
        job = _fake_job(id=5, module_type_id=1, data_entry_type_id=10)
        lookup = _build_job_lookup([job])
        assert (1, 10) in lookup
        assert lookup[(1, 10)].job_id == 5

    def test_skips_none_id(self):
        job = _fake_job(id=None)
        lookup = _build_job_lookup([job])
        assert len(lookup) == 0

    def test_empty_list(self):
        assert _build_job_lookup([]) == {}

    def test_none_enums(self):
        job = _fake_job(
            ingestion_method=None, target_type=None, state=None, result=None
        )
        lookup = _build_job_lookup([job])
        summary = lookup[(2, 20)]
        assert summary.ingestion_method == 0
        assert summary.target_type is None
        assert summary.state is None
        assert summary.result is None


# ---------------------------------------------------------------------------
# _build_jobs_list
# ---------------------------------------------------------------------------
class TestBuildJobsList:
    def test_builds_list(self):
        jobs = [_fake_job(id=1), _fake_job(id=2, module_type_id=3)]
        result = _build_jobs_list(jobs)
        assert len(result) == 2

    def test_skips_none_id(self):
        result = _build_jobs_list([_fake_job(id=None)])
        assert len(result) == 0


# ---------------------------------------------------------------------------
# _enrich_config_with_jobs
# ---------------------------------------------------------------------------
class TestEnrichConfigWithJobs:
    def test_injects_job(self):
        config = {"modules": {"2": {"submodules": {"20": {}}}}}
        job = _fake_job()
        lookup = _build_job_lookup([job])
        _enrich_config_with_jobs(config, lookup)
        assert config["modules"]["2"]["submodules"]["20"]["latest_job"] is not None

    def test_no_matching_job(self):
        config = {"modules": {"99": {"submodules": {"99": {}}}}}
        _enrich_config_with_jobs(config, {})
        assert config["modules"]["99"]["submodules"]["99"]["latest_job"] is None

    def test_non_dict_module_skipped(self):
        config = {"modules": {"bad": "string_value"}}
        _enrich_config_with_jobs(config, {})  # no crash

    def test_non_numeric_keys_skipped(self):
        config = {"modules": {"abc": {"submodules": {"xyz": {}}}}}
        _enrich_config_with_jobs(config, {})
        # xyz should not have latest_job since keys aren't numeric
        assert "latest_job" not in config["modules"]["abc"]["submodules"]["xyz"]

    def test_empty_modules(self):
        config = {"modules": {}}
        _enrich_config_with_jobs(config, {})  # no crash


# ---------------------------------------------------------------------------
# _deep_merge
# ---------------------------------------------------------------------------
class TestDeepMerge:
    def test_simple_merge(self):
        result = _deep_merge({"a": 1}, {"b": 2})
        assert result == {"a": 1, "b": 2}

    def test_override(self):
        result = _deep_merge({"a": 1}, {"a": 2})
        assert result == {"a": 2}

    def test_nested_merge(self):
        base = {"a": {"x": 1, "y": 2}}
        patch = {"a": {"y": 3, "z": 4}}
        result = _deep_merge(base, patch)
        assert result == {"a": {"x": 1, "y": 3, "z": 4}}

    def test_does_not_mutate_base(self):
        base = {"a": {"x": 1}}
        _deep_merge(base, {"a": {"y": 2}})
        assert "y" not in base["a"]

    def test_patch_replaces_non_dict(self):
        result = _deep_merge({"a": "string"}, {"a": {"nested": True}})
        assert result == {"a": {"nested": True}}


# ---------------------------------------------------------------------------
# generate_unique_filename
# ---------------------------------------------------------------------------
class TestGenerateUniqueFilename:
    def test_preserves_extension(self):
        name = generate_unique_filename("report.csv")
        assert name.endswith(".csv")
        assert name.startswith("report_")

    def test_strips_directory(self):
        name = generate_unique_filename("../../etc/passwd")
        assert "/" not in name
        assert name.startswith("passwd_")

    def test_no_extension(self):
        name = generate_unique_filename("noext")
        assert name.startswith("noext_")

    def test_unique(self):
        n1 = generate_unique_filename("file.csv")
        n2 = generate_unique_filename("file.csv")
        assert n1 != n2


# ---------------------------------------------------------------------------
# get_files_storage_path
# ---------------------------------------------------------------------------
class TestGetFilesStoragePath:
    def test_default(self, monkeypatch):
        monkeypatch.delenv("FILES_STORAGE_PATH", raising=False)
        assert get_files_storage_path() == "./files_storage"

    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("FILES_STORAGE_PATH", "/custom/path")
        assert get_files_storage_path() == "/custom/path"
