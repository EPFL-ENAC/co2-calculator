"""Tests for the backend-computed "Incomplete" flag (#1215).

Mandatoriness rule: only ``factor`` and ``reference`` uploads are
mandatory. ``data`` (CSV) and ``api_data`` do NOT drive the flag.

Computation rule: ``incomplete`` iff a mandatory job is *missing* (no
row). An errored job (``result == 2``) is NOT missing — the upload-card
surfaces error state independently. The errored-job test below is the
issue-#1215 regression invariant.
"""

from app.api.v1.year_configuration import _enrich_config_with_incomplete_flags


def _sub(latest_factor_job=None, latest_reference_job=None, **extra) -> dict:
    """Build a submodule dict matching the shape after
    ``_enrich_config_with_jobs``.
    """
    sub: dict = {
        "enabled": True,
        "threshold": None,
        "latest_data_job": None,
        "latest_factor_job": latest_factor_job,
        "latest_reference_job": latest_reference_job,
        "latest_api_data_job": None,
    }
    sub.update(extra)
    return sub


def _job(result: int = 0) -> dict:
    """Build a minimal job dict — only fields the helper inspects."""
    return {"result": result}


def _module(submodules: dict, latest_common_factor_job=None, **extra) -> dict:
    mod: dict = {
        "enabled": True,
        "uncertainty_tag": "medium",
        "submodules": submodules,
        "latest_common_data_job": None,
        "latest_common_factor_job": latest_common_factor_job,
    }
    mod.update(extra)
    return mod


# ---------------------------------------------------------------------------
# 4-quadrant matrix on a mandatory-factor + mandatory-reference submodule
# (train: module_type_id=2, data_entry_type_id=21).
# ---------------------------------------------------------------------------


class TestSubmoduleMatrix:
    def test_factor_present_reference_present(self):
        config = {
            "modules": {
                "2": _module({"21": _sub(_job(), _job())}),
            }
        }
        _enrich_config_with_incomplete_flags(config)
        sub = config["modules"]["2"]["submodules"]["21"]
        assert sub["incomplete"] is False
        assert sub["incomplete_reasons"] == []

    def test_factor_missing_reference_present(self):
        config = {
            "modules": {
                "2": _module({"21": _sub(None, _job())}),
            }
        }
        _enrich_config_with_incomplete_flags(config)
        sub = config["modules"]["2"]["submodules"]["21"]
        assert sub["incomplete"] is True
        assert sub["incomplete_reasons"] == ["missing_factor"]

    def test_factor_present_reference_missing(self):
        config = {
            "modules": {
                "2": _module({"21": _sub(_job(), None)}),
            }
        }
        _enrich_config_with_incomplete_flags(config)
        sub = config["modules"]["2"]["submodules"]["21"]
        assert sub["incomplete"] is True
        assert sub["incomplete_reasons"] == ["missing_reference"]

    def test_factor_missing_reference_missing(self):
        config = {
            "modules": {
                "2": _module({"21": _sub(None, None)}),
            }
        }
        _enrich_config_with_incomplete_flags(config)
        sub = config["modules"]["2"]["submodules"]["21"]
        assert sub["incomplete"] is True
        assert sub["incomplete_reasons"] == ["missing_factor", "missing_reference"]


# ---------------------------------------------------------------------------
# Regression pin for issue #1215: an errored job is NOT missing.
# Before the fix, the frontend treated ``result != 0`` as incomplete —
# which left the badge stuck on after a successful re-upload because
# the previous job's error never cleared the flag.
# ---------------------------------------------------------------------------


class TestErroredJobNotMissing:
    def test_errored_factor_with_success_reference_is_not_incomplete(self):
        """Issue #1215 regression: errored job ≠ missing."""
        config = {
            "modules": {
                "2": _module(
                    {"21": _sub(_job(result=2), _job(result=0))},
                ),
            }
        }
        _enrich_config_with_incomplete_flags(config)
        sub = config["modules"]["2"]["submodules"]["21"]
        assert sub["incomplete"] is False
        assert sub["incomplete_reasons"] == []

    def test_errored_data_job_does_not_make_submodule_incomplete(self):
        """``data`` (CSV) is not mandatory — its error must not raise the flag."""
        sub_dict = _sub(_job(), _job())
        sub_dict["latest_data_job"] = _job(result=2)
        config = {"modules": {"2": _module({"21": sub_dict})}}
        _enrich_config_with_incomplete_flags(config)
        assert config["modules"]["2"]["submodules"]["21"]["incomplete"] is False


# ---------------------------------------------------------------------------
# Module-level rollup
# ---------------------------------------------------------------------------


class TestModuleAggregation:
    def test_any_enabled_submodule_incomplete_makes_module_incomplete(self):
        config = {
            "modules": {
                "2": _module(
                    {
                        "21": _sub(_job(), _job()),  # complete
                        "20": _sub(None, _job()),  # missing factor
                    }
                ),
            }
        }
        _enrich_config_with_incomplete_flags(config)
        assert config["modules"]["2"]["incomplete"] is True

    def test_disabled_incomplete_submodule_does_not_raise_module(self):
        sub_disabled = _sub(None, None)
        sub_disabled["enabled"] = False
        config = {
            "modules": {
                "2": _module(
                    {
                        "21": _sub(_job(), _job()),  # complete, enabled
                        "20": sub_disabled,  # incomplete but disabled
                    }
                ),
            }
        }
        _enrich_config_with_incomplete_flags(config)
        assert config["modules"]["2"]["incomplete"] is False

    def test_all_submodules_complete_module_complete(self):
        config = {
            "modules": {
                "2": _module(
                    {
                        "21": _sub(_job(), _job()),
                        "20": _sub(_job(), _job()),
                    }
                ),
            }
        }
        _enrich_config_with_incomplete_flags(config)
        assert config["modules"]["2"]["incomplete"] is False

    def test_disabled_module_never_incomplete(self):
        """A disabled module's badge stays off even with missing mandatories."""
        disabled = _module({"21": _sub(None, None)})
        disabled["enabled"] = False
        config = {"modules": {"2": disabled}}
        _enrich_config_with_incomplete_flags(config)
        assert config["modules"]["2"]["incomplete"] is False

    def test_disabled_common_factor_module_never_incomplete(self):
        """Disabled common-factor module: missing common-factor is irrelevant."""
        disabled = _module({"10": _sub()}, latest_common_factor_job=None)
        disabled["enabled"] = False
        config = {"modules": {"4": disabled}}
        _enrich_config_with_incomplete_flags(config)
        assert config["modules"]["4"]["incomplete"] is False


# ---------------------------------------------------------------------------
# Common-factor modules (Equipment Electric Consumption = 4, Purchase = 5).
# Submodules are ``noFactors``; factors come from the module-level upload.
# ---------------------------------------------------------------------------


class TestCommonFactorModules:
    def test_module_with_common_factor_present_is_complete(self):
        config = {
            "modules": {
                "4": _module(
                    {
                        "10": _sub(),  # no factor, no reference (mandatoriness=False)
                        "11": _sub(),
                        "12": _sub(),
                    },
                    latest_common_factor_job=_job(),
                ),
            }
        }
        _enrich_config_with_incomplete_flags(config)
        assert config["modules"]["4"]["incomplete"] is False
        for sub_key in ("10", "11", "12"):
            assert config["modules"]["4"]["submodules"][sub_key]["incomplete"] is False

    def test_module_with_missing_common_factor_is_incomplete(self):
        config = {
            "modules": {
                "4": _module(
                    {
                        "10": _sub(),
                        "11": _sub(),
                        "12": _sub(),
                    },
                    latest_common_factor_job=None,
                ),
            }
        }
        _enrich_config_with_incomplete_flags(config)
        assert config["modules"]["4"]["incomplete"] is True

    def test_errored_common_factor_is_not_missing(self):
        """An errored common-factor job exists — module is not incomplete."""
        config = {
            "modules": {
                "4": _module(
                    {"10": _sub()},
                    latest_common_factor_job=_job(result=2),
                ),
            }
        }
        _enrich_config_with_incomplete_flags(config)
        assert config["modules"]["4"]["incomplete"] is False

    def test_common_factor_satisfies_mandatory_submodule_factor(self):
        """When a module's common-factor exists, per-submodule mandatory
        factor is satisfied even without a per-submodule factor job.
        """
        # purchase additional_purchases (5, 67) has mandatory_factor=True
        config = {
            "modules": {
                "5": _module(
                    {"67": _sub(latest_factor_job=None)},
                    latest_common_factor_job=_job(),
                ),
            }
        }
        _enrich_config_with_incomplete_flags(config)
        assert config["modules"]["5"]["submodules"]["67"]["incomplete"] is False


# ---------------------------------------------------------------------------
# Edge cases — defensive handling
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_unknown_submodule_pair_defaults_to_no_mandatoriness(self):
        """A submodule not in the mandatoriness table defaults to no
        mandatory uploads — safer than guessing.
        """
        config = {"modules": {"99": _module({"99": _sub(None, None)})}}
        _enrich_config_with_incomplete_flags(config)
        assert config["modules"]["99"]["submodules"]["99"]["incomplete"] is False
        assert config["modules"]["99"]["incomplete"] is False

    def test_non_numeric_module_key_skipped(self):
        config = {"modules": {"abc": _module({"99": _sub(None, None)})}}
        _enrich_config_with_incomplete_flags(config)
        # Module key wasn't parseable as int — helper should not
        # crash and should not write a flag.
        assert "incomplete" not in config["modules"]["abc"]

    def test_non_dict_submodule_value_skipped(self):
        config = {"modules": {"2": {"submodules": {"21": "bad"}, "enabled": True}}}
        _enrich_config_with_incomplete_flags(config)
        # The submodule entry stayed a string; the module-level flag
        # was still computed (against an empty enabled-sub set).
        assert config["modules"]["2"]["incomplete"] is False

    def test_empty_modules(self):
        config: dict = {"modules": {}}
        _enrich_config_with_incomplete_flags(config)
        assert config == {"modules": {}}
