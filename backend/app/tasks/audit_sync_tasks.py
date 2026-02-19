"""Background tasks for audit synchronization with Elasticsearch.

Implements periodic sync of pending audit records and retry of failed records.
Uses FastAPI's BackgroundTasks for scheduled operations.
"""

from typing import Any, Dict

from fastapi import BackgroundTasks

from app.core.logging import get_logger
from app.db import SessionLocal
from app.services.audit_sync_service import AuditSyncService

logger = get_logger(__name__)


async def sync_pending_audit_records_task() -> Dict[str, Any]:
    """
    Background task to sync pending audit records with Elasticsearch.

    This task should be scheduled to run periodically (e.g., every 5 minutes).
    """
    try:
        # Manage session lifecycle properly with context manager
        async with SessionLocal() as db:
            sync_service = AuditSyncService(db)
            result = await sync_service.sync_pending_audit_records(batch_size=500)

            logger.info(f"Background sync task completed: {result}")

            return result
    except Exception as e:
        logger.error(f"Error in background sync task: {e}")
        return {"error": str(e)}


async def retry_failed_audit_records_task(max_retries: int = 3) -> Dict[str, Any]:
    """
    Background task to retry failed audit records with Elasticsearch.

    This task should be scheduled to run less frequently (e.g., every hour).
    """
    try:
        # Manage session lifecycle properly with context manager
        async with SessionLocal() as db:
            sync_service = AuditSyncService(db)
            result = await sync_service.retry_failed_audit_records(
                max_retries=max_retries
            )

            logger.info(f"Background retry task completed: {result}")

            return result
    except Exception as e:
        logger.error(f"Error in background retry task: {e}")
        return {"error": str(e)}


async def sync_audit_records_with_elasticsearch(
    background_tasks: BackgroundTasks,
) -> Dict[str, Any]:
    """
    Main entry point for syncing audit records with Elasticsearch.

    This function can be called from API endpoints or scheduled tasks.
    """
    # Schedule the sync task - each task manages its own database session
    background_tasks.add_task(sync_pending_audit_records_task)

    # Schedule the retry task (run less frequently)
    # In production, this would be scheduled separately via a task queue
    background_tasks.add_task(retry_failed_audit_records_task)

    return {"status": "sync tasks scheduled"}
