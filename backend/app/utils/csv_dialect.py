"""Delimiter detection for CSV files that may use ',' or ';' (Excel locales)."""

import csv
import io
from typing import Any

_SNIFF_SAMPLE_SIZE = 8192


def detect_csv_delimiter(csv_text: str) -> str:
    """Detect whether csv_text uses ',' or ';' as its delimiter.

    Falls back to ',' when sniffing is inconclusive (e.g. a single-column
    file, or an empty sample).
    """
    sample = csv_text[:_SNIFF_SAMPLE_SIZE]
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;").delimiter
    except csv.Error:
        return ","


def csv_dict_reader(csv_text: str, **kwargs: Any) -> csv.DictReader:
    """Build a csv.DictReader over csv_text, auto-detecting ',' vs ';'."""
    return csv.DictReader(
        io.StringIO(csv_text, newline=""),
        delimiter=detect_csv_delimiter(csv_text),
        **kwargs,
    )
