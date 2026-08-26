import hashlib
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.factor_taxonomy_cache import TaxonomyCacheEntry, started_year_cache
from app.core.logging import get_logger
from app.models.data_entry import DataEntryTypeEnum
from app.models.module_type import get_module_type_for_data_entry_type
from app.models.user import User, UserProvider
from app.schemas.data_entry import BaseModuleHandler
from app.schemas.taxonomy import TaxonomyNode
from app.services.module_handler_service import ModuleHandlerService
from app.services.year_config_service import is_year_started

logger = get_logger(__name__)

router = APIRouter()

# Cache-Control split by the year lifecycle invariant (#2391 decision 2):
# once a year is started, its factors never change again, so a browser can
# hold the response for a full day. A year still in preparation can be
# re-ingested at any moment and a browser cache is unreachable by the
# write-time broadcast (#2280), so it keeps a short max-age — the ETag
# below makes those frequent revalidations cheap 304s either way.
_CACHE_CONTROL_STARTED = "private, max-age=86400"
_CACHE_CONTROL_PREPARING = "private, max-age=60"


def _cache_control_for(started: bool) -> str:
    return _CACHE_CONTROL_STARTED if started else _CACHE_CONTROL_PREPARING


async def _is_year_started_cached(
    db: AsyncSession, year: int, provider: UserProvider
) -> bool:
    """Cached ``is_year_started`` lookup (#2391 decision 2).

    Without this, the batch route's ~11 entries would each re-query
    year_configuration for a value that's identical across all of them.
    See ``started_year_cache``'s docstring for why a short TTL is safe.
    """
    key = (year, provider)
    cached = started_year_cache.get(key)
    if cached is not None:
        return cached
    started = await is_year_started(db, year, provider)
    started_year_cache.set(key, started)
    return started


async def get_taxonomy_for_data_entry_type(
    response: Response,
    data_entry_type: DataEntryTypeEnum,
    year: int,
    db: AsyncSession,
    current_user: User,
) -> TaxonomyCacheEntry:
    """Resolve the cache entry (tree + ETag) for a data entry type.

    Plain function, not a route — the only HTTP-facing callers are the
    single-entry and batch routes below, via `_resolve_module_data_entry_
    taxonomy`. Sets the Cache-Control header so both routes carry it; the
    ETag travels back on the returned entry so each route can also set it
    and answer `If-None-Match` (#2391 decision 2).
    """
    module_type = get_module_type_for_data_entry_type(data_entry_type)
    if not module_type:
        raise HTTPException(status_code=404, detail="Module type not found")
    # Taxonomies are year-parameterized classification metadata with no unit
    # data; authentication is the only gate — the simulators render every
    # module's form for any unit member.
    handler = BaseModuleHandler.get_by_type(data_entry_type)
    handler_service = ModuleHandlerService(db)
    entry = await handler_service.get_taxonomy_with_etag(handler, data_entry_type, year)
    started = await _is_year_started_cached(db, year, current_user.provider)
    response.headers["Cache-Control"] = _cache_control_for(started)
    return entry


async def _resolve_module_data_entry_taxonomy(
    response: Response,
    module: str,
    data_entry: str,
    year: int,
    db: AsyncSession,
    current_user: User,
) -> TaxonomyCacheEntry:
    """Resolve one data entry's cache entry, validating it belongs to module.

    Shared by the single-entry and batch routes so both stay one source
    of truth for the module/data-entry validation.
    """
    data_entry_name = data_entry.replace("-", "_")
    data_entry_type = (
        DataEntryTypeEnum[data_entry_name]
        if data_entry_name in DataEntryTypeEnum.__members__
        else None
    )
    if not data_entry_type:
        raise HTTPException(status_code=404, detail="Data entry type not found")
    module_type = get_module_type_for_data_entry_type(data_entry_type)
    if not module_type:
        raise HTTPException(status_code=404, detail="Module type not found")
    if module_type.name != module.replace("-", "_"):
        raise HTTPException(
            status_code=400,
            detail=f"Data entry type {data_entry} does not belong to module {module}",
        )
    return await get_taxonomy_for_data_entry_type(
        response, data_entry_type, year, db, current_user
    )


def _not_modified(response: Response) -> Response:
    """304 short-circuit that keeps whatever headers were already set.

    Returning a `Response` instance directly makes FastAPI skip
    `response_model` serialization entirely — the point of answering
    `If-None-Match` here rather than after building the JSON body.
    """
    return Response(status_code=304, headers=dict(response.headers))


def _combine_etags(etags: list[str]) -> str:
    """One deterministic ETag for a batch of per-entry ETags (#2391).

    Sorted so the combined value depends only on which entries actually
    resolved, never on the `entries=` query param order.
    """
    payload = "".join(sorted(etags)).encode()
    return f'"{hashlib.sha256(payload).hexdigest()}"'


@router.get(
    # Must stay registered before "/module/{module}/{data_entry}" below --
    # Starlette matches routes in registration order and that route's
    # {data_entry} path param would otherwise swallow this literal path too.
    "/module/{module}/data-entries",
    response_model=dict[str, TaxonomyNode],
    response_model_exclude_none=True,
)
async def get_taxonomies_for_module_data_entries(
    response: Response,
    module: str,
    entries: list[str] = Query(
        ..., description="Data entry type names to fetch taxonomy for"
    ),
    year: int = Query(
        default_factory=lambda: datetime.now().year,
        description="Year for which to retrieve the taxonomy",
    ),
    if_none_match: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, TaxonomyNode] | Response:
    """Batch-fetch taxonomies for several data entry types of one module.

    Collapses a report page's ~11 sequential /module/{module}/{data_entry}
    round trips into one call per module (#2049 T6). Each entry still
    resolves through get_taxonomy_for_data_entry_type, so it hits/populates
    the same (data_entry_type, year) cache a single-entry call would.

    The response ETag combines every resolved entry's own ETag (#2391
    decision 2); a matching `If-None-Match` short-circuits with an empty
    304 before any tree is serialized to JSON.

    An ``HTTPException`` (bad entry name, entry not in this module) means
    the request itself is malformed — that's not one submodule's problem,
    it propagates and fails the whole batch. Any other exception is a
    per-entry runtime failure (e.g. a transient DB hiccup) and must not
    blank every other, already-resolved entry in the batch (#2258
    follow-up) — logged loud and the entry is left out of the response
    rather than silently rendered as an empty taxonomy.
    """
    results: dict[str, TaxonomyNode] = {}
    etags: list[str] = []
    for entry in entries:
        try:
            cache_entry = await _resolve_module_data_entry_taxonomy(
                response, module, entry, year, db, current_user
            )
        except HTTPException:
            raise
        except Exception:
            # A DB-level error leaves the shared session's transaction
            # aborted -- every subsequent entry would fail too without
            # this, turning one bad entry into "the rest of the batch
            # went blank" (#2258 follow-up). Roll back before logging:
            # logging a SQLAlchemy exception can trigger lazy-load
            # __repr__ calls on ORM instances, which would themselves
            # hit the still-aborted session.
            await db.rollback()
            logger.exception(
                "get_taxonomies_for_module_data_entries: entry %r of module "
                "%r failed, omitting it from the batch response",
                entry,
                module,
            )
            continue
        results[entry] = cache_entry.tree
        etags.append(cache_entry.etag)

    combined_etag = _combine_etags(etags)
    response.headers["ETag"] = combined_etag
    if if_none_match == combined_etag:
        return _not_modified(response)
    return results


@router.get(
    "/module/{module}/{data_entry}",
    response_model=TaxonomyNode,
    response_model_exclude_none=True,
)
async def get_taxonomy_for_module_data_entry(
    response: Response,
    module: str,
    data_entry: str,
    year: int = Query(
        default_factory=lambda: datetime.now().year,
        description="Year for which to retrieve the taxonomy",
    ),
    if_none_match: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaxonomyNode | Response:
    """Get taxonomy for a given module and data entry type.

    A matching `If-None-Match` short-circuits with an empty 304 before the
    tree is serialized to JSON (#2391 decision 2).
    """
    cache_entry = await _resolve_module_data_entry_taxonomy(
        response, module, data_entry, year, db, current_user
    )
    response.headers["ETag"] = cache_entry.etag
    if if_none_match == cache_entry.etag:
        return _not_modified(response)
    return cache_entry.tree
