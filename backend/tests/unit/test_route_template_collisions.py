"""Regression test for co2-calculator#2260 (route-compartmentalization).

``opentelemetry-instrumentation-asgi``'s ``_collect_target_attribute`` (the
function behind the ``http.target`` label on the ``http.server.duration``
metric) builds its value from ``scope["route"].path_format`` -- and FastAPI
(0.141.1, pinned here) sets ``scope["route"]`` to each endpoint's *original*
route object, i.e. the path exactly as declared on its own ``APIRouter``,
before any ancestor ``include_router(prefix=...)`` call ever combines it with
a prefix. Two endpoints that happen to declare the same local leaf path
(e.g. ``/{year}`` under two different sub-routers) therefore collapse onto
an identical ``http.target``, even though FastAPI itself can tell them apart.

``fastapi.routing.iter_route_contexts`` -- the same public function
``opentelemetry-instrumentation-fastapi`` uses internally to compute the
correct ``http.route`` attribute -- resolves the fully-prefixed path
instead. This test pins both halves of that gap directly against the real
router (no opentelemetry install needed): the leaf collision that explains
today's ``http.target`` behaviour, and the full-path invariant that would
hold if observability moved to ``http.route``.
"""

from fastapi.routing import iter_route_contexts

from app.main import app


def _route_contexts():
    return list(iter_route_contexts(app.routes))


def test_year_configuration_leaf_paths_collide_like_http_target():
    """GET/PATCH/POST .../year-configuration/{year} each declare their own
    leaf path as "/{year}" -- the exact shape that made three semantically
    different endpoints collapse onto the identical http.target
    "/api/{year}" in production (see co2-calculator#2260, and
    docs/src/implementation-plans/1402-trim-down-alerting.md's "Done" log).
    """
    leaf_paths_by_method: dict[str, set[str]] = {}
    for rc in _route_contexts():
        original = rc.original_route
        path_format = getattr(original, "path_format", None)
        if path_format != "/{year}":
            continue
        for method in rc.methods or set():
            leaf_paths_by_method.setdefault(method, set()).add(path_format)

    assert leaf_paths_by_method.get("GET") == {"/{year}"}
    assert leaf_paths_by_method.get("PATCH") == {"/{year}"}
    assert leaf_paths_by_method.get("POST") == {"/{year}"}


def test_full_route_templates_have_no_path_method_collisions():
    """The invariant path-based observability actually needs: no two routes
    share the same (fully-prefixed path template, HTTP methods) pair. This
    is what http.route resolves to via iter_route_contexts -- unlike
    http.target, which only ever sees the un-prefixed leaf path and is
    blind to every ancestor include_router(prefix=...).
    """
    seen: dict[tuple[str, frozenset], str] = {}
    duplicates: list[tuple[str, frozenset, str, str]] = []

    for rc in _route_contexts():
        path_format = rc.path_format
        if path_format is None:
            continue
        key = (path_format, frozenset(rc.methods or set()))
        if key in seen:
            duplicates.append((*key, seen[key], rc.name))
        else:
            seen[key] = rc.name

    assert duplicates == []
