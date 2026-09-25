"""Off-request side effects of a session renewal (#2943)."""

from app.core.logging import get_logger
from app.db import SessionLocal
from app.models.audit import AuditChangeTypeEnum
from app.services.audit_service import AuditDocumentService

logger = get_logger(__name__)


async def audit_session_renewal(
    *,
    user_id: int,
    institutional_id: str | None,
    email: str | None,
    ip_address: str | None,
    route_path: str,
    renewed_exp: int,
) -> None:
    """One audit row per cookie renewal, same shape as a login or logout row.

    Runs as a background task with its own session so the request that
    triggered the renewal never commits inside its auth dependency. A
    failure is logged at ERROR with the ``audit_failure`` marker the
    alerting keys on, like every other auth audit write.

    ``renewed_exp`` is the ``exp`` of the cookie being replaced: the parallel
    requests of one page load each renew the same cookie, and this is the
    key that groups their rows into one renewal.
    """
    handler_id = institutional_id or str(user_id)
    async with SessionLocal() as session:
        try:
            await AuditDocumentService(session).create_version(
                entity_type="User",
                entity_id=user_id,
                data_snapshot={
                    "event": "renewal",
                    "user_id": user_id,
                    "email": email,
                    "institutional_id": institutional_id,
                    "renewed_exp": renewed_exp,
                },
                change_type=AuditChangeTypeEnum.UPDATE,
                changed_by=user_id,
                change_reason="Session renewed",
                handler_id=handler_id,
                handled_ids=[institutional_id] if institutional_id else [],
                ip_address=ip_address,
                route_path=route_path,
            )
            await session.commit()
        except Exception as exc:
            logger.error(
                "Auth audit log failed",
                extra={
                    "error": str(exc),
                    "change_type": AuditChangeTypeEnum.UPDATE,
                    "audit_failure": True,
                },
            )
