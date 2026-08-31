"""Regression for #2295's table matrix finding: an unknown ``sort_by``
must surface as a client error, never a 500.

The repo raises ValueError for a key outside the handler's sort_map; the
submodule route wraps it into a 400 (``carbon_report_module.get_submodule``).
The live probe for the wrapping is ``table_matrix.py``'s bad-sort check;
this pins the raise the route depends on.
"""

import pydantic
import pytest

from app.repositories.data_entry_repo import DataEntryRepository, UnknownSortField


def test_unknown_sort_key_raises_unknown_sort_field():
    repo = DataEntryRepository.__new__(DataEntryRepository)
    with pytest.raises(UnknownSortField, match="Cannot sort by unknown field"):
        repo._apply_sort(None, "__nope__", "asc", {"id": object()})


def test_unknown_sort_field_is_narrower_than_pydantic_validation_error():
    """The route catches UnknownSortField only.

    pydantic's ValidationError also subclasses ValueError; if the route caught
    ValueError, a corrupt stored row failing its response DTO would be
    reported as a 400 client error instead of the 500 it is.
    """
    assert issubclass(UnknownSortField, ValueError)
    assert not issubclass(pydantic.ValidationError, UnknownSortField)
