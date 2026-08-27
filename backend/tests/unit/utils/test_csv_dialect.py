from app.utils.csv_dialect import csv_dict_reader, detect_csv_delimiter


def test_detect_comma_delimiter():
    text = "a,b,c\n1,2,3\n4,5,6\n"

    assert detect_csv_delimiter(text) == ","


def test_detect_semicolon_delimiter():
    text = "a;b;c\n1;2;3\n4;5;6\n"

    assert detect_csv_delimiter(text) == ";"


def test_detect_semicolon_delimiter_with_quoted_commas():
    # Excel-exported file: semicolon-separated, but a quoted field contains
    # commas that a naive detector could mistake for the delimiter.
    text = 'name;note\nfoo;"a, b, c"\nbar;"d, e"\n'

    assert detect_csv_delimiter(text) == ";"


def test_detect_falls_back_to_comma_for_single_column():
    text = "a\n1\n2\n"

    assert detect_csv_delimiter(text) == ","


def test_detect_falls_back_to_comma_for_empty_text():
    assert detect_csv_delimiter("") == ","


def test_detect_uses_only_sniff_sample():
    # A delimiter mismatch beyond the sniff sample must not affect the
    # detected delimiter for the header/first rows.
    header = "a,b,c\n1,2,3\n"
    padding = "x" * 10_000
    text = header + padding + "\nsemicolons;here;now\n"

    assert detect_csv_delimiter(text) == ","


def test_csv_dict_reader_parses_comma_file():
    text = "a,b,c\n1,2,3\n4,5,6\n"

    rows = list(csv_dict_reader(text))

    assert rows == [
        {"a": "1", "b": "2", "c": "3"},
        {"a": "4", "b": "5", "c": "6"},
    ]


def test_csv_dict_reader_parses_semicolon_file():
    text = "a;b;c\n1;2;3\n4;5;6\n"

    rows = list(csv_dict_reader(text))

    assert rows == [
        {"a": "1", "b": "2", "c": "3"},
        {"a": "4", "b": "5", "c": "6"},
    ]


def test_csv_dict_reader_preserves_embedded_newlines_in_quoted_fields():
    text = 'a;b\n"line1\nline2";2\n'

    rows = list(csv_dict_reader(text))

    assert rows == [{"a": "line1\nline2", "b": "2"}]


def test_csv_dict_reader_forwards_kwargs():
    text = "1,2,3\n4,5,6\n"

    rows = list(csv_dict_reader(text, fieldnames=["x", "y", "z"]))

    assert rows == [
        {"x": "1", "y": "2", "z": "3"},
        {"x": "4", "y": "5", "z": "6"},
    ]
