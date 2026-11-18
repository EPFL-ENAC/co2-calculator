"""CSV cells must not be runnable as spreadsheet formulas (#3185)."""

import csv
import io
import re
from pathlib import Path

import pytest

import app.api.v1 as api_v1
from app.utils.csv_safe import SafeCsvWriter, csv_safe


@pytest.mark.parametrize(
    "cell",
    ["=HYPERLINK(1)", "+1+1", "-1+1", "@SUM(A1)", "\tcmd", "\rcmd"],
)
def test_csv_safe_prefixes_a_formula(cell):
    assert csv_safe(cell) == "'" + cell


@pytest.mark.parametrize("cell", ["plain", "a=b", "", 12.5, -12.5, None])
def test_csv_safe_leaves_other_cells_alone(cell):
    assert csv_safe(cell) == cell


def test_writer_neutralizes_every_cell():
    output = io.StringIO()

    SafeCsvWriter(output).writerow(["=1+1", "ok", -3])

    assert next(csv.reader(io.StringIO(output.getvalue()))) == ["'=1+1", "ok", "-3"]


def test_no_route_writes_csv_without_neutralizing():
    """A bare csv.writer in a route is how three exports missed the helper."""
    api_dir = Path(api_v1.__file__).parent
    offenders = [
        path.name
        for path in api_dir.glob("*.py")
        if re.search(r"\bcsv\.(writer|DictWriter)\(", path.read_text())
    ]
    assert offenders == []
