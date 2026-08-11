"""On-demand factor resolution (plan 1661).

The entry's classification fields are the source of truth; the matching
factor is derived state — resolved when needed, memoized per instance,
never persisted on the entry.  Instance lifetime: one API request or one
recalc slice.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.data_entry import DataEntryTypeEnum
from app.models.factor import Factor
from app.repositories.factor_repo import FactorRepository
from app.schemas.data_entry import BaseModuleHandler

if TYPE_CHECKING:
    from app.schemas.data_entry import ModuleHandler


@dataclass
class _FactorMaps:
    # ``by_kind_subkind`` and the ``override_lookup``/``kind_lookup`` pair
    # are mutually exclusive: ``_build_maps`` fills one or the other based
    # on the handler's ``kind_field_override``; the unused side stays {}.
    by_id: dict[int, Factor]
    by_kind_subkind: dict[tuple[str, str | None], int]
    override_lookup: dict[str, list[tuple[int, str]]]
    kind_lookup: dict[str, list[tuple[int, str | None]]]


class FactorResolver:
    """Resolves the Factor matching a data entry's classification fields.

    Replaces the persisted ``primary_factor_id`` rematch that used to run
    inside ``EmissionRecalculationWorkflow``: the same kind/subkind and
    override-key-first rules, computed on demand and memoized per
    ``(data_entry_type, year)`` for the resolver's lifetime instead of
    written back onto the entry.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._maps: dict[tuple[int, int], _FactorMaps] = {}

    async def factors_by_id(
        self, data_entry_type: DataEntryTypeEnum, year: int
    ) -> dict[int, Factor]:
        maps = await self._get_maps(data_entry_type, year)
        return maps.by_id

    async def resolve(
        self,
        handler: ModuleHandler,
        data: dict,
        data_entry_type: DataEntryTypeEnum,
        year: int,
    ) -> Factor | None:
        # Falsy kind (field undeclared, key absent, empty value) resolves to
        # None BEFORE the bulk load — callers never need their own gate, and
        # Strategy-B entries (kind derived at compute time, absent from
        # data) cost nothing here.
        if handler.kind_field is None or not data.get(handler.kind_field):
            return None
        maps = await self._get_maps(data_entry_type, year)
        if handler.kind_field_override is not None:
            factor_id = _resolve_with_override(
                data,
                kind_field=handler.kind_field,
                override_field=handler.kind_field_override,
                override_lookup=maps.override_lookup,
                kind_lookup=maps.kind_lookup,
            )
        else:
            factor_id = _resolve_kind_subkind(
                data,
                kind_field=handler.kind_field,
                subkind_field=handler.subkind_field,
                by_kind_subkind=maps.by_kind_subkind,
            )
        if factor_id is None:
            return None
        return maps.by_id.get(factor_id)

    async def _get_maps(
        self, data_entry_type: DataEntryTypeEnum, year: int
    ) -> _FactorMaps:
        key = (data_entry_type.value, year)
        maps = self._maps.get(key)
        if maps is None:
            handler = BaseModuleHandler.get_by_type(data_entry_type)
            factors = await FactorRepository(self.session).list_by_data_entry_type(
                data_entry_type, year
            )
            maps = _build_maps(
                factors,
                kind_field=handler.kind_field,
                subkind_field=handler.subkind_field,
                override_field=handler.kind_field_override,
            )
            self._maps[key] = maps
        return maps


def _build_maps(
    factors: list[Factor],
    *,
    kind_field: str | None,
    subkind_field: str | None,
    override_field: str | None,
) -> _FactorMaps:
    """Build the id / kind-subkind / override / kind lookup maps from one
    bulk-fetched factor set.

    Mirrors the per-slice map building formerly in
    ``EmissionRecalculationWorkflow.recalculate_for_data_entry_type``
    (kind/subkind and override-key-first branches): one bulk SELECT feeds
    every lookup structure so resolving many entries costs O(1) dict
    lookups instead of one query per entry. Built unconditionally —
    callers gate on ``kind_field`` before calling ``resolve``.
    """
    by_id: dict[int, Factor] = {f.id: f for f in factors if f.id is not None}
    if kind_field is None:
        return _FactorMaps(by_id, {}, {}, {})
    if override_field is not None:
        override_lookup, kind_lookup = _build_override_maps(
            factors, kind_field, override_field
        )
        return _FactorMaps(by_id, {}, override_lookup, kind_lookup)
    by_kind_subkind = _build_kind_subkind_map(factors, kind_field, subkind_field)
    return _FactorMaps(by_id, by_kind_subkind, {}, {})


def _build_override_maps(
    factors: list[Factor], kind_field: str, override_field: str
) -> tuple[dict[str, list[tuple[int, str]]], dict[str, list[tuple[int, str | None]]]]:
    """override_code → [(factor_id, kind_value)] and kind_value →
    [(factor_id, override_code | None)], for the override-key-first lookup.
    """
    override_lookup: dict[str, list[tuple[int, str]]] = {}
    kind_lookup: dict[str, list[tuple[int, str | None]]] = {}
    for factor in factors:
        if factor.id is None:
            continue
        classification = factor.classification or {}
        kind_value = classification.get(kind_field)
        if not kind_value:
            continue
        ov_code: str | None = classification.get(override_field) or None
        kind_lookup.setdefault(kind_value, []).append((factor.id, ov_code))
        if ov_code:
            override_lookup.setdefault(ov_code, []).append((factor.id, kind_value))
    return override_lookup, kind_lookup


def _build_kind_subkind_map(
    factors: list[Factor], kind_field: str, subkind_field: str | None
) -> dict[tuple[str, str | None], int]:
    """(kind, subkind) → factor_id, first writer wins on duplicate keys —
    matches the recalc's in-memory dict build (Phase 2 makes duplicates
    impossible).
    """
    by_kind_subkind: dict[tuple[str, str | None], int] = {}
    for factor in factors:
        if factor.id is None:
            continue
        classification = factor.classification or {}
        kind_value = classification.get(kind_field)
        if kind_value is None or kind_value == "":
            continue
        subkind_value = _normalize_subkind(classification, subkind_field)
        by_kind_subkind.setdefault((kind_value, subkind_value), factor.id)
    return by_kind_subkind


def _normalize_subkind(classification: dict, subkind_field: str | None) -> str | None:
    if not subkind_field:
        return None
    raw = classification.get(subkind_field)
    return raw if raw else None


def _resolve_kind_subkind(
    data: dict,
    *,
    kind_field: str,
    subkind_field: str | None,
    by_kind_subkind: dict[tuple[str, str | None], int],
) -> int | None:
    """Resolve a factor id via the kind→subkind→kind-only fallback chain.

    1. Exact ``(kind, subkind)`` match.
    2. Kind-only ``(kind, None)`` fallback — only tried when a subkind
       was supplied (otherwise the exact match above already tried it).

    Returns ``None`` on overall miss. Subkind normalises empty string to
    ``None``. Precondition: ``resolve()`` already guaranteed a truthy kind.
    """
    kind = data[kind_field]
    subkind: str | None = None
    if subkind_field:
        raw = data.get(subkind_field)
        subkind = raw if raw else None
    factor_id = by_kind_subkind.get((kind, subkind))
    if factor_id is not None:
        return factor_id
    if subkind is not None:
        return by_kind_subkind.get((kind, None))
    return None


def _resolve_with_override(
    data: dict,
    *,
    kind_field: str,
    override_field: str,
    override_lookup: dict[str, list[tuple[int, str]]],
    kind_lookup: dict[str, list[tuple[int, str | None]]],
) -> int | None:
    """Resolve a factor id using the override-key-first rule.

    1. If the entry carries a value for ``override_field``, look it up in
       ``override_lookup`` (override_code → [(factor_id, kind_value)]). A
       single match wins; multiple matches are disambiguated by kind.
    2. Kind-only fallback via ``kind_lookup`` (kind_value →
       [(factor_id, override_code | None)]): a single row wins outright;
       several rows sharing the kind narrow to the "average" rows (those
       without an override code) — there must be exactly one.

    Returns ``None`` when no factor in the current set matches. Raises
    ``ValueError`` on ambiguous data. Precondition: ``resolve()`` already
    guaranteed a truthy kind.
    """
    kind = data[kind_field]
    code: str | None = data.get(override_field) or None
    if code:
        matches = override_lookup.get(code, [])
        if matches:
            return _pick_override_match(matches, kind, kind_field, override_field, code)
        # code present but no factor carries it → fall through to kind fallback
    return _pick_kind_average(kind_lookup.get(kind, []), kind, kind_field)


def _pick_override_match(
    matches: list[tuple[int, str]],
    kind: str,
    kind_field: str,
    override_field: str,
    code: str,
) -> int:
    """A single override-code match wins outright; several are disambiguated
    by the entry's kind; still-ambiguous data raises.
    """
    if len(matches) == 1:
        return matches[0][0]
    same_kind = [fid for fid, kv in matches if kv == kind]
    if len(same_kind) == 1:
        return same_kind[0]
    raise ValueError(
        f"Ambiguous factor data: {len(matches)} factors match "
        f"{override_field}={code!r} and {kind_field}={kind!r} "
        f"cannot disambiguate"
    )


def _pick_kind_average(
    kind_matches: list[tuple[int, str | None]], kind: str, kind_field: str
) -> int | None:
    """No override code on the entry: a single row for the kind wins
    outright; several rows narrow to the "average" rows (no override
    code) — there must be exactly one.
    """
    if not kind_matches:
        return None
    if len(kind_matches) == 1:
        return kind_matches[0][0]
    averages = [fid for fid, ov in kind_matches if ov is None]
    if len(averages) == 1:
        return averages[0]
    raise ValueError(
        f"Ambiguous factor data: {len(kind_matches)} factors match "
        f"{kind_field}={kind!r} with {len(averages)} average rows "
        f"(need exactly 1)"
    )
