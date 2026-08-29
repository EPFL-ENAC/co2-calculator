"""Regression for #2295's table matrix finding: an unknown ``sort_by``
must surface as a client error, never a 500.

The repo raises ValueError for a key outside the handler's sort_map; the
submodule route wraps it into a 400 (``carbon_report_module.get_submodule``).
The live probe for the wrapping is ``table_matrix.py``'s bad-sort check;
this pins the raise the route depends on.
"""

import pytest

from app.repositories.data_entry_repo import DataEntryRepository


def test_unknown_sort_key_raises_value_error():
    repo = DataEntryRepository.__new__(DataEntryRepository)
    with pytest.raises(ValueError, match="Cannot sort by unknown field"):
        repo._apply_sort(None, "__nope__", "asc", {"id": object()})
