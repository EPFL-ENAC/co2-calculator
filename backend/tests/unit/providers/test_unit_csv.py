"""Units from a CSV file (#500): the unit source without Accred."""

import pytest

from app.models.user import UserProvider
from app.providers import unit_provider as unit_provider_module
from app.providers.unit_csv import read_units_csv
from app.providers.unit_provider import DatabaseUnitProvider

HEADER = (
    "institutional_code,institutional_id,name,level,parent_institutional_code,"
    "label_en,label_fr,is_active\n"
)
TREE = (
    HEADER
    + "1,U1,UNIV,1,,University,Université,\n"
    + "2,U2,SCHOOL,2,1,School,École,true\n"
    + "3,U3,LAB,3,2,Lab,Laboratoire,false\n"
)


def _write(tmp_path, content: str) -> str:
    path = tmp_path / "units.csv"
    path.write_text(content, encoding="utf-8")
    return str(path)


def test_paths_and_parent_ids_come_from_the_parent_chain(tmp_path):
    rows = {
        row["institutional_code"]: row for row in read_units_csv(_write(tmp_path, TREE))
    }

    lab = rows["3"]
    assert lab["path_institutional_code"] == "1 2 3"
    assert lab["path_institutional_id"] == "U1 U2 U3"
    assert lab["path_name"] == "UNIV SCHOOL LAB"
    assert lab["parent_institutional_id"] == "U2"
    assert lab["is_active"] is False
    assert rows["1"]["parent_institutional_id"] is None
    assert rows["1"]["is_active"] is True


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (HEADER + "1,U1,UNIV,1,,,,\n1,U1,UNIV,1,,,,\n", "duplicate"),
        (HEADER + "1,U1,UNIV,1,,,,\n2,U2,LAB,2,9,,,\n", "not in the file"),
        (HEADER + "1,U1,UNIV,1,,,,\n2,U2,LAB,3,1,,,\n", "parent's level"),
        (HEADER + "1,U1,UNIV,2,,,,\n", "level 1"),
        (HEADER + "1,,UNIV,1,,,,\n", "institutional_id is empty"),
        ("institutional_code,name\n1,UNIV\n", "missing columns"),
    ],
)
def test_a_wrong_file_fails_with_the_reason(tmp_path, content, message):
    with pytest.raises(ValueError, match=message):
        read_units_csv(_write(tmp_path, content))


def test_no_file_configured_fails_loudly():
    with pytest.raises(ValueError, match="UNITS_CSV_PATH is not set"):
        read_units_csv("")


async def test_the_database_provider_syncs_the_csv_units(tmp_path, monkeypatch):
    monkeypatch.setattr(
        unit_provider_module.settings, "UNITS_CSV_PATH", _write(tmp_path, TREE)
    )
    provider = DatabaseUnitProvider(db_session=None)

    units_raw, principal_users = await provider.fetch_all_units()
    units = [provider.map_api_unit(raw) for raw in units_raw]

    assert principal_users == []
    assert {unit.institutional_id for unit in units} == {"U1", "U2", "U3"}
    assert all(unit.provider == UserProvider.DEFAULT for unit in units)
