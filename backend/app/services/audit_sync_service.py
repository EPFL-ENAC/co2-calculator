"""Audit synchronization service for Elasticsearch integration.

Implements the sync status pattern for reliable synchronization of audit records
with Elasticsearch:
    pending -> syncing -> synced/failed with retry capability.
"""

from datetime import datetime
from typing import Any, Dict

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.elasticsearch.client import ElasticsearchClient
from app.models.audit import AuditDocument, SyncStatusEnum
from app.repositories.audit_repo import AuditDocumentRepository

logger = get_logger(__name__)
settings = get_settings()


class AuditSyncService:
    """Service for synchronizing audit records with Elasticsearch."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = AuditDocumentRepository(session)
        self.es_client = ElasticsearchClient()

    async def sync_single_audit_record(self, audit_id: int) -> bool:
        """
        Sync a single audit record to Elasticsearch with status tracking.

        Uses the pattern: pending -> syncing -> synced/failed

        Args:
            audit_id: ID of the audit record to sync

        Returns:
            bool: True if sync was successful, False otherwise
        """
        try:
            # Get the audit record
            audit_record = await self.repo.get_by_id(audit_id)
            if not audit_record:
                logger.warning(f"Audit record {audit_id} not found")
                return False

            # Skip if already synced
            if audit_record.sync_status == SyncStatusEnum.SYNCED:
                logger.info(f"Audit record {audit_id} already synced")
                return True

            # Skip if already failed and we don't want to retry
            if (
                audit_record.sync_status == SyncStatusEnum.FAILED
                and audit_record.sync_error
            ):
                logger.info(
                    f"Audit record {audit_id} previously failed: "
                    f"{audit_record.sync_error}"
                )
                return False

            # Update status to syncing
            audit_record.sync_status = SyncStatusEnum.SYNCING
            audit_record.synced_at = None
            audit_record.sync_error = None
            self.session.add(audit_record)
            await self.session.flush()

            # Sync with Elasticsearch
            audit_dict = {
                "id": audit_record.id,
                "entity_type": audit_record.entity_type,
                "entity_id": audit_record.entity_id,
                "version": audit_record.version,
                "change_type": audit_record.change_type,
                "change_reason": audit_record.change_reason,
                "changed_by": audit_record.changed_by,
                "changed_at": audit_record.changed_at,
                "handler_id": audit_record.handler_id,
                "handled_ids": audit_record.handled_ids,
                "ip_address": audit_record.ip_address,
                "route_path": audit_record.route_path,
                "route_payload": audit_record.route_payload,
                "previous_hash": audit_record.previous_hash,
                "current_hash": audit_record.current_hash,
                "synced_at": audit_record.synced_at,
            }

            success = self.es_client.sync_audit_record(audit_dict)

            if success:
                # Update status to synced
                audit_record.sync_status = SyncStatusEnum.SYNCED
                audit_record.synced_at = datetime.utcnow()
                audit_record.sync_error = None
                logger.info(
                    f"Audit record {audit_id} successfully synced to Elasticsearch"
                )
            else:
                # Update status to failed
                audit_record.sync_status = SyncStatusEnum.FAILED
                audit_record.sync_error = "Failed to sync to Elasticsearch"
                logger.error(f"Audit record {audit_id} failed to sync to Elasticsearch")

            self.session.add(audit_record)
            await self.session.flush()
            await self.session.commit()
            return success

        except Exception as e:
            logger.error(f"Error syncing audit record {audit_id}: {e}")
            # Update status to failed on exception
            try:
                audit_record = await self.repo.get_by_id(audit_id)
                if audit_record:
                    audit_record.sync_status = SyncStatusEnum.FAILED
                    audit_record.sync_error = str(e)
                    self.session.add(audit_record)
                    await self.session.flush()
                    await self.session.commit()
            except Exception as inner_e:
                logger.error(
                    f"Failed to update sync status for audit record {audit_id}: "
                    f"{inner_e}"
                )

            return False

    async def sync_pending_audit_records(self, batch_size: int = 100) -> Dict[str, Any]:
        """
        Sync all pending audit records in batches.

        Args:
            batch_size: Number of records to process in each batch

        Returns:
            Dict with statistics about the sync operation
        """
        try:
            # Define records to skip based on entity_type or handler_id from config
            skip_entity_types = set(
                et.strip()
                for et in settings.AUDIT_SYNC_SKIP_ENTITY_TYPES.split(",")
                if et.strip()
            )
            skip_handler_ids = set(
                hid.strip()
                for hid in settings.AUDIT_SYNC_SKIP_HANDLER_IDS.split(",")
                if hid.strip()
            )

            # Find all pending records
            stmt = (
                select(AuditDocument)
                .where(AuditDocument.sync_status == SyncStatusEnum.PENDING)
                .where(col(AuditDocument.synced_at).is_(None))
                .limit(batch_size)
            )

            result = await self.session.exec(stmt)
            all_pending_records = list(result.all())

            if not all_pending_records:
                logger.info("No pending audit records to sync")
                return {"synced": 0, "failed": 0, "skipped": 0, "total": 0}

            # Separate records to sync vs skip
            records_to_sync = []
            records_to_skip = []

            for record in all_pending_records:
                if (
                    record.entity_type in skip_entity_types
                    or record.handler_id in skip_handler_ids
                ):
                    records_to_skip.append(record)
                else:
                    records_to_sync.append(record)

            # Mark skipped records
            skipped_count = 0
            for record in records_to_skip:
                record.sync_status = SyncStatusEnum.SKIPPED
                record.synced_at = datetime.utcnow()
                record.sync_error = None
                self.session.add(record)
                skipped_count += 1

            # Update status to syncing for records to be synced
            for record in records_to_sync:
                record.sync_status = SyncStatusEnum.SYNCING
                record.synced_at = None
                record.sync_error = None
                self.session.add(record)

            await self.session.flush()

            # Prepare records for Elasticsearch sync (only non-skipped records)
            audit_dicts = [
                {
                    "id": record.id,
                    "entity_type": record.entity_type,
                    "entity_id": record.entity_id,
                    "version": record.version,
                    "change_type": record.change_type,
                    "change_reason": record.change_reason,
                    "changed_by": record.changed_by,
                    "changed_at": record.changed_at,
                    "handler_id": record.handler_id,
                    "handled_ids": record.handled_ids,
                    "ip_address": record.ip_address,
                    "route_path": record.route_path,
                    "route_payload": record.route_payload,
                    "previous_hash": record.previous_hash,
                    "current_hash": record.current_hash,
                    "synced_at": record.synced_at,
                }
                for record in records_to_sync
            ]

            # Bulk sync with Elasticsearch (only non-skipped records)
            if audit_dicts:
                sync_stats = self.es_client.bulk_sync_audit_records(audit_dicts)
            else:
                sync_stats = {"success": 0, "failed": 0, "errors": [], "conflicts": []}

            # Update statuses based on sync results
            success_count = 0
            failed_count = 0
            conflict_count = 0

            # Create sets for faster lookup
            error_ids = {item["id"] for item in sync_stats.get("errors", [])}
            conflict_ids = {item["id"] for item in sync_stats.get("conflicts", [])}

            # Update records based on their sync result
            for record in records_to_sync:
                if record.id in conflict_ids:
                    # This record had a version conflict - document already exists in ES
                    # Treat as successful sync
                    record.sync_status = SyncStatusEnum.SYNCED
                    record.synced_at = datetime.utcnow()
                    record.sync_error = None
                    conflict_count += 1
                elif record.id in error_ids:
                    # This record failed for other reasons
                    record.sync_status = SyncStatusEnum.FAILED
                    record.sync_error = "Failed to sync to Elasticsearch"
                    failed_count += 1
                else:
                    # This record succeeded
                    record.sync_status = SyncStatusEnum.SYNCED
                    record.synced_at = datetime.utcnow()
                    record.sync_error = None
                    success_count += 1

                self.session.add(record)

            await self.session.flush()
            await self.session.commit()

            logger.info(
                f"Bulk sync completed: {success_count} synced, {conflict_count} "
                f"conflicts, {failed_count} failed, {skipped_count} skipped"
            )

            return {
                "synced": success_count,
                "conflicts": conflict_count,
                "failed": failed_count,
                "skipped": skipped_count,
                "total": len(all_pending_records),
                "es_stats": sync_stats,
            }

        except Exception as e:
            logger.error(f"Error in bulk sync operation: {e}")
            return {"synced": 0, "failed": 0, "total": 0, "error": str(e)}

    async def retry_failed_audit_records(self, max_retries: int = 3) -> Dict[str, Any]:
        """
        Retry syncing failed audit records.

        Args:
            max_retries: Maximum number of times to retry each failed record

        Returns:
            Dict with statistics about the retry operation
        """
        try:
            # Find failed records that haven't exceeded max retries
            stmt = (
                select(AuditDocument)
                .where(AuditDocument.sync_status == SyncStatusEnum.FAILED)
                .where(col(AuditDocument.sync_error).is_not(None))
            )
            result = await self.session.exec(stmt)
            failed_records = list(result.all())

            if not failed_records:
                logger.info("No failed audit records to retry")
                return {"retried": 0, "success": 0, "failed": 0}

            retry_count = 0
            success_count = 0
            still_failed_count = 0
            records_processed = False  # Track if any records were actually processed

            for record in failed_records:
                # Check if we've exceeded max retries
                # we might want to store retry count
                if record.sync_error and "Retry limit exceeded" in record.sync_error:
                    still_failed_count += 1
                    continue

                if record.id is None:
                    logger.error(f"Failed record with missing ID: {record}")
                    still_failed_count += 1
                    continue

                # Mark that we're processing at least one record
                records_processed = True

                # Try to sync
                success = await self.sync_single_audit_record(record.id)
                retry_count += 1

                if success:
                    success_count += 1
                else:
                    # Update error message to indicate retry attempt
                    if record.sync_error:
                        record.sync_error += " (retry attempt)"
                    else:
                        record.sync_error = "Retry attempt failed"
                    still_failed_count += 1

                self.session.add(record)
                await self.session.flush()

            # Only commit if we actually processed records
            if records_processed:
                await self.session.commit()

            logger.info(
                f"Retry completed: {retry_count} attempted, "
                f"{success_count} successful, {still_failed_count} still failed"
            )

            return {
                "retried": retry_count,
                "success": success_count,
                "failed": still_failed_count,
            }

        except Exception as e:
            logger.error(f"Error in retry operation: {e}")
            return {"retried": 0, "success": 0, "failed": 0, "error": str(e)}
