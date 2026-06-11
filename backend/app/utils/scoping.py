"""Affiliation-scoping helpers shared by backoffice routers (#459, #862).

The pure permission utilities live in ``app.utils.permissions`` and stay
free of SQLAlchemy / FastAPI. This module owns the SQL-level predicate that
maps a backoffice scope (a set of unit cfs) onto the unit subtree, plus the
gate helper that raises 403 when the caller is not a backoffice user.
"""

from fastapi import Depends, HTTPException, status
from sqlalchemy import and_, exists, func, or_
from sqlalchemy.orm import aliased
from sqlalchemy.sql.elements import ColumnElement
from sqlmodel import col

from app.core.security import get_current_active_user
from app.models.unit import Unit
from app.models.user import User
from app.utils.permissions import derive_backoffice_affiliations, has_permission


def build_scope_subtree_predicate(scope_cfs: set[str]) -> ColumnElement[bool]:
    """SQL predicate selecting units within the subtree of any scope cf (#862).

    A backoffice scope token is a unit cf (``institutional_id``) at any level.
    A row is in scope iff some anchor unit ``A`` with ``A.institutional_id`` in
    ``scope_cfs`` has its ``institutional_code`` as a token of the row's
    ``path_institutional_code`` (the indexed, self-inclusive code path), so the
    anchor itself and all its descendants match. Token-boundary matching avoids
    false positives like code ``142`` matching ``1420``.
    """
    anchor = aliased(Unit)
    code = anchor.institutional_code
    path = col(Unit.path_institutional_code)
    token_match = or_(
        path == code,
        path.like(func.concat(code, " %")),
        path.like(func.concat("% ", code)),
        path.like(func.concat("% ", code, " %")),
    )
    return exists().where(
        and_(col(anchor.institutional_id).in_(scope_cfs), token_match)
    )


def gate_backoffice(
    user: User,
    action: str = "view",
    anchor_path: str = "backoffice.reporting",
) -> tuple[bool, set[str]]:
    """Authorize ``<anchor_path>:<action>`` under any scope; return scope.

    Raises 403 if the user holds neither the bare ``anchor_path`` key nor any
    ``anchor_path/<aff>`` key granting ``action``. Returns
    ``(is_global, affiliations)``; callers pass ``affiliations`` as ``scope_cfs``
    to the report repo, or apply ``build_scope_subtree_predicate`` on a unit
    query, when ``is_global`` is False.

    The default anchor is ``backoffice.reporting`` — the only affiliation-scoped
    backoffice area (#862), and therefore the only one whose affiliations can be
    derived. Scope-less backoffice pages (users, documentation, ui_texts,
    configuration, pipeline_operations, logs) gate via ``require_permission``
    instead, not this helper.

    Uses ``has_permission(..., any_scope=True)`` because affiliation-scoped
    users only hold ``<anchor>/<aff>`` keys — ``require_permission``'s
    literal-path lookup would 403 them.
    """
    perms = user.calculate_permissions()
    if not has_permission(perms, anchor_path, action, any_scope=True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )
    return derive_backoffice_affiliations(perms, anchor_path=anchor_path)


def require_any_scope(action: str = "view", anchor_path: str = "backoffice.reporting"):
    """FastAPI dependency factory: gate ``<anchor_path>:<action>`` any-scope.

    Drop-in replacement for ``require_permission`` for routes that only need
    the 403 gate, not the ``(is_global, affiliations)`` tuple. For routes
    that filter data by affiliation, call ``gate_backoffice`` inside the
    handler instead.

    Example::

        @router.get("/jobs")
        async def list_jobs(
            current_user: User = Depends(
                require_any_scope("view", "backoffice.pipeline_operations")
            ),
            ...
        ):
    """

    async def _dep(
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        gate_backoffice(current_user, action=action, anchor_path=anchor_path)
        return current_user

    return _dep


def can_view_module_flow(user: User) -> bool:
    """True if the user may read module-flow pipeline/job status (#862).

    Allowed for any module user who can *sync* at least one module
    (``modules.<name>.sync`` — the status endpoints track sync/ingestion
    progress, so only sync-capable users dispatch and need to poll it; a
    standard user with view/edit but no sync does not) or a backoffice
    configuration operator (``backoffice.configuration`` view, the Data
    Management page). A metier user without configuration sees none.
    """
    perms = user.calculate_permissions()
    if has_permission(perms, "backoffice.configuration", "view"):
        return True
    return any(
        key.startswith("modules.") and "sync" in (actions or [])
        for key, actions in (perms or {}).items()
    )


def require_module_or_config_view():
    """FastAPI dependency gating module-flow status reads.

    See ``can_view_module_flow`` for the allow rule.

    The Configuration / Data-Management page and the module upload pages both
    poll these job/pipeline status endpoints (the latter for a principal's own
    uploads), so the gate mirrors ``/dispatch``'s dual model.
    """

    async def _dep(
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        if not can_view_module_flow(current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied",
            )
        return current_user

    return _dep
