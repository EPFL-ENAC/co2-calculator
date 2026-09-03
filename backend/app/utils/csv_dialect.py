"""Dialect handling for CSV files: ',' vs ';' (Excel locales) and comments."""

import csv
import io
from typing import Any

_SNIFF_SAMPLE_SIZE = 8192

# Templates ship their filling instructions inline, prefixed with this
# marker, so the guidance travels with the file and a user who forgets to
# delete it before uploading doesn't get it imported as data (#2026).
COMMENT_PREFIX = "#"


def strip_comment_lines(csv_text: str) -> str:
    """Drop instruction lines from csv_text.

    A line counts as a comment only when COMMENT_PREFIX opens it and the
    parser is at a record boundary: a '#' that opens a physical line
    *inside* a quoted multi-line field is data, not a comment. Quote
    parity tracks that boundary — under RFC 4180 an escaped quote is a
    pair, so an odd count is what flips a record open or closed.
    """
    kept: list[str] = []
    inside_quoted_field = False

    for line in csv_text.splitlines(keepends=True):
        if not inside_quoted_field and line.lstrip("﻿").startswith(COMMENT_PREFIX):
            continue
        if line.count('"') % 2:
            inside_quoted_field = not inside_quoted_field
        kept.append(line)

    return "".join(kept)


def detect_csv_delimiter(csv_text: str) -> str:
    """Detect whether csv_text uses ',' as its delimiter, or ';'.

    Falls back to ',' when sniffing is inconclusive (e.g. a single-column
    file, or an empty sample).
    """
    sample = csv_text[:_SNIFF_SAMPLE_SIZE]
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;").delimiter
    except csv.Error:
        return ","


def csv_dict_reader(csv_text: str, **kwargs: Any) -> csv.DictReader:
    """Build a csv.DictReader over csv_text, minus its comment lines.

    Comments are stripped before sniffing so prose commas in an
    instruction block can't sway the detected delimiter.
    """
    uncommented = strip_comment_lines(csv_text)
    return csv.DictReader(
        io.StringIO(uncommented, newline=""),
        delimiter=detect_csv_delimiter(uncommented),
        **kwargs,
    )
