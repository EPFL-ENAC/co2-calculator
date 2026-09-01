"""The CSV templates the app offers for download must be importable.

Every file under ``frontend/public/templates`` is what a user downloads,
fills in and uploads back, so it has to survive the same decode/parse path
as any other upload. #2026 shipped a pack that failed on all three counts
at once (latin-1 bytes, US-format dates, instruction rows read as data).
"""

import csv
import io
import re
from pathlib import Path

import pytest

from app.utils.csv_dialect import csv_dict_reader, strip_comment_lines

TEMPLATES_DIR = (
    Path(__file__).resolve().parents[3] / "frontend" / "public" / "templates"
)
US_DATE = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")


def _templates() -> list[Path]:
    paths = sorted(TEMPLATES_DIR.glob("*.csv"))
    if not paths:
        raise AssertionError(f"No CSV templates found in {TEMPLATES_DIR}")
    return paths


@pytest.mark.parametrize("path", _templates(), ids=lambda p: p.name)
def test_template_decodes_as_utf8(path: Path) -> None:
    raw = path.read_bytes()

    assert raw.startswith(b"\xef\xbb\xbf"), (
        "template must keep its UTF-8 BOM so Excel round-trips accents (#2069)"
    )
    raw.decode("utf-8-sig")  # the exact call the ingestion path makes


@pytest.mark.parametrize("path", _templates(), ids=lambda p: p.name)
def test_template_parses_with_no_instruction_rows_left(path: Path) -> None:
    text = path.read_bytes().decode("utf-8-sig")
    reader = csv_dict_reader(text)
    rows = list(reader)

    assert reader.fieldnames, "template has no header row"
    leaked = [
        i
        for i, row in enumerate(rows, start=1)
        if any((value or "").lstrip().startswith("#") for value in row.values())
    ]
    assert not leaked, f"instruction rows reached the importer as data: {leaked}"

    # A stripped # only proves the marker is there. An instruction row that
    # lost its marker (a typo'd "Instructons:" header, a quoted wrapped
    # sentence) parses as data and slips past the check above, so hunt the
    # prose itself. Values that legitimately contain these words stay in
    # comment lines, never in data cells.
    prose = re.compile(r"(?i)instruct|times per day \(|delete (these|all)")
    worded = [
        (i, value)
        for i, row in enumerate(rows, start=1)
        for value in row.values()
        if value and prose.search(value)
    ]
    assert not worded, f"instruction prose reached the importer as data: {worded}"


@pytest.mark.parametrize("path", _templates(), ids=lambda p: p.name)
def test_template_has_no_mojibake(path: Path) -> None:
    """UTF-8 text re-encoded through cp1252 stays valid UTF-8, so the decode
    test can't catch it — but 'Ã©' where 'é' belongs breaks the exact-match
    factor lookups and shows broken accents to users (found by #2323 review).
    """
    text = path.read_bytes().decode("utf-8-sig")

    hits = [
        (i, line[:80])
        for i, line in enumerate(text.splitlines(), start=1)
        if re.search(r"[ÂÃ].|â€", line)
    ]
    assert not hits, f"double-encoded UTF-8 (mojibake) in: {hits}"


@pytest.mark.parametrize("path", _templates(), ids=lambda p: p.name)
def test_template_example_rows_have_no_us_format_dates(path: Path) -> None:
    text = path.read_bytes().decode("utf-8-sig")

    offenders = [
        value
        for row in csv_dict_reader(text)
        for value in row.values()
        if value and US_DATE.match(value.strip())
    ]

    assert not offenders, (
        f"dates must be ISO YYYY-MM-DD, the importer rejects {offenders}"
    )


@pytest.mark.parametrize("path", _templates(), ids=lambda p: p.name)
def test_template_rows_match_the_header_width(path: Path) -> None:
    text = path.read_bytes().decode("utf-8-sig")

    rows = list(csv.reader(io.StringIO(strip_comment_lines(text), newline="")))
    width = len(rows[0])

    ragged = [i for i, row in enumerate(rows, start=1) if len(row) != width]

    assert not ragged, f"rows {ragged} do not have {width} columns"
