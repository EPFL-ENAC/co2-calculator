"""#2007 — `use` bounds per `use_unit`.

The same field means a share of a platform (%), machine time (hours), spend
(CHF) or animal housings depending on which platform was picked, and `use`
divides straight into the platform's footprint: 150% of CAM-GE would claim one
and a half times the whole platform's emissions.
"""

import pytest
from pydantic import ValidationError

from app.modules.research_facilities.data_entries import (
    ResearchFacilitiesAnimalHandlerCreate,
    ResearchFacilitiesAnimalHandlerUpdate,
    ResearchFacilitiesCommonHandlerCreate,
    ResearchFacilitiesCommonHandlerUpdate,
)

_COMMON_BASE = {"data_entry_type_id": 70, "carbon_report_module_id": 1}
_ANIMAL_BASE = {"data_entry_type_id": 71, "carbon_report_module_id": 1}


def _common(use: float, use_unit: str) -> dict:
    return {
        **_COMMON_BASE,
        "researchfacility_id": "0872",
        "researchfacility_name": "CAM-GE",
        "use": use,
        "use_unit": use_unit,
    }


def _animal(use: float, use_unit: str = "housings") -> dict:
    return {
        **_ANIMAL_BASE,
        "researchfacility_id": "1321",
        "researchfacility_name": "CPG",
        "researchfacility_type": "rodent",
        "use": use,
        "use_unit": use_unit,
    }


@pytest.mark.parametrize("use", [0, 1, 99.5, 100])
def test_percent_within_range_accepted(use):
    ResearchFacilitiesCommonHandlerCreate(**_common(use, "%"))


@pytest.mark.parametrize("use", [100.01, 150, 1000])
def test_percent_above_hundred_rejected(use):
    with pytest.raises(ValidationError, match="at most 100"):
        ResearchFacilitiesCommonHandlerCreate(**_common(use, "%"))


@pytest.mark.parametrize("use,ok", [(8760, True), (8760.5, False), (20000, False)])
def test_hours_capped_at_a_year(use, ok):
    if ok:
        ResearchFacilitiesCommonHandlerCreate(**_common(use, "hours"))
        return
    with pytest.raises(ValidationError, match="at most 8760"):
        ResearchFacilitiesCommonHandlerCreate(**_common(use, "hours"))


def test_chf_has_no_upper_bound():
    # Platform spend has no meaningful ceiling — SPC-GE's own total is >10M.
    ResearchFacilitiesCommonHandlerCreate(**_common(10_616_982.72, "CHF"))


def test_fractional_housings_rejected():
    with pytest.raises(ValidationError, match="whole number"):
        ResearchFacilitiesAnimalHandlerCreate(**_animal(2.5))


def test_whole_housings_accepted():
    ResearchFacilitiesAnimalHandlerCreate(**_animal(258))


def test_unknown_unit_is_unbounded():
    """Another institution may use a unit this deployment has never seen; the
    hardcoded table must not reject it (min 0 still applies via the field
    validator).
    """
    ResearchFacilitiesCommonHandlerCreate(**_common(999_999, "kWh"))


def test_bounds_apply_on_update_too():
    # The workflow overlays persisted data before validating, so use_unit is
    # present even when the PATCH only carries `use`.
    with pytest.raises(ValidationError, match="at most 100"):
        ResearchFacilitiesCommonHandlerUpdate(**_common(120, "%"))
    with pytest.raises(ValidationError, match="whole number"):
        ResearchFacilitiesAnimalHandlerUpdate(**_animal(2.5))


def test_update_without_unit_is_not_bounded():
    """A PATCH that carries neither field cannot be judged — the workflow's
    overlay supplies them on the real path.
    """
    ResearchFacilitiesCommonHandlerUpdate(
        **_COMMON_BASE, researchfacility_name="CAM-GE"
    )
