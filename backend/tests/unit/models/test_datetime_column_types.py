"""Every datetime column declares its SQL type instead of inheriting
SQLModel's default for a bare ``datetime`` field.

SQLModel 0.0.47 turned that default into ``UTCDateTime`` (timestamptz that
raises on naive values). Four columns inherited it silently: year
configuration writes broke, and the models drifted from the migrations,
which declare them ``timestamp``. A library bump must never change a
column's type or write contract behind the migrations' back.
"""

import importlib
import pkgutil

from sqlmodel import SQLModel
from sqlmodel.sql.sqltypes import UTCDateTime

import app.models


def _load_all_models() -> None:
    for module in pkgutil.walk_packages(app.models.__path__, app.models.__name__ + "."):
        importlib.import_module(module.name)


def test_no_column_inherits_sqlmodel_default_datetime_type():
    _load_all_models()
    inherited = [
        f"{table.name}.{column.name}"
        for table in SQLModel.metadata.sorted_tables
        for column in table.columns
        if isinstance(column.type, UTCDateTime)
    ]
    assert inherited == [], (
        f"declare sa_type (or sa_column) on these datetime fields: {inherited}"
    )
