"""Fast ``default_factory`` wrappers for SQLModel ``Field``.

Pydantic's ``resolve_default_value`` calls ``inspect.signature()`` on every
``default_factory`` on every model instantiation — not cached per-field, see
``pydantic._internal._fields.takes_validated_data_argument`` — to check
whether it accepts a ``validated_data`` argument. For a bare C builtin
(``dict``, ``datetime.utcnow``) that lookup is expensive and always fails:
measured ~20µs/call for ``datetime.utcnow`` this way, ~10x a plain Python
function's ~2µs (plan #2050 §C2 follow-up — the same construction-cost class
found in ``DataEntryEmission``, here one level up in every ``table=True``
model that defaults a dict/timestamp). Use these instead of passing the
builtin directly as ``default_factory``.
"""

from datetime import datetime


def default_dict() -> dict:
    return {}


def default_list() -> list:
    return []


def default_utcnow() -> datetime:
    return datetime.utcnow()
