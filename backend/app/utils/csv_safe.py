"""CSV export cells that a spreadsheet cannot run as formulas."""

import csv
from collections.abc import Iterable
from typing import Any, TextIO

_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def csv_safe(value: Any) -> Any:
    """Neutralize a string cell that a spreadsheet would read as a formula."""
    if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value


class SafeCsvWriter:
    """A ``csv.writer`` that neutralizes every cell, so an export can't forget."""

    def __init__(self, stream: TextIO) -> None:
        self._writer = csv.writer(stream)

    def writerow(self, row: Iterable[Any]) -> None:
        self._writer.writerow([csv_safe(cell) for cell in row])
