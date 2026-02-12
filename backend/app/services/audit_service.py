"""Document versioning service for audit trail.

Provides append-only versioning with hash chain integrity for any entity type.
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.audit import AuditDocument
from app.repositories.audit_repo import AuditDocumentRepository

logger = get_logger(__name__)


class AuditDocumentService:
    """
    Service for managing document versions with audit trail.

    This service:
    - Creates immutable version records for any entity
    - Computes JSON diffs between versions
    - Maintains hash chain for tamper detection
    - Supports rollback by creating new versions
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = AuditDocumentRepository(session)

    def _compute_hash(
        self,
        entity_type: str,
        entity_id: int,
        version: int,
        data_snapshot: Dict,
        previous_hash: Optional[str],
    ) -> str:
        """Compute SHA-256 hash for version integrity."""
        payload = json.dumps(
            {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "version": version,
                "data_snapshot": data_snapshot,
                "previous_hash": previous_hash or "",
            },
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(payload.encode()).hexdigest()

    def _compute_diff(self, old_data: Optional[Dict], new_data: Dict) -> Optional[Dict]:
        """
        Compute a simple diff between old and new data.

        Returns a dict with:
        - added: keys in new but not in old
        - removed: keys in old but not in new
        - changed: keys with different values
        """
        if old_data is None:
            return None

        diff: Dict[str, Any] = {"added": {}, "removed": {}, "changed": {}}

        old_keys = set(old_data.keys())
        new_keys = set(new_data.keys())

        # Added keys
        for key in new_keys - old_keys:
            diff["added"][key] = new_data[key]

        # Removed keys
        for key in old_keys - new_keys:
            diff["removed"][key] = old_data[key]

        # Changed keys
        for key in old_keys & new_keys:
            if old_data[key] != new_data[key]:
                diff["changed"][key] = {"old": old_data[key], "new": new_data[key]}

        # Return None if no changes
        if not diff["added"] and not diff["removed"] and not diff["changed"]:
            return None

        return diff

    async def get_current_version(
        self, entity_type: str, entity_id: int
    ) -> Optional[AuditDocument]:
        """Get the current (is_current=True) version for an entity."""
        stmt = select(AuditDocument).where(
            col(AuditDocument.entity_type) == entity_type,
            col(AuditDocument.entity_id) == entity_id,
            col(AuditDocument.is_current) == True,  # noqa: E712
        )
        result = await self.session.exec(stmt)
        return result.one_or_none()

    async def get_version(
        self, entity_type: str, entity_id: int, version: int
    ) -> Optional[AuditDocument]:
        """Get a specific version of an entity."""
        stmt = select(AuditDocument).where(
            col(AuditDocument.entity_type) == entity_type,
            col(AuditDocument.entity_id) == entity_id,
            col(AuditDocument.version) == version,
        )
        result = await self.session.exec(stmt)
        return result.one_or_none()

    async def get_version_at_time(
        self,
        entity_type: str,
        entity_id: int,
        timestamp: datetime,
    ) -> Optional[AuditDocument]:
        """Get the version that was current at a specific timestamp."""
        stmt = (
            select(AuditDocument)
            .where(
                col(AuditDocument.entity_type) == entity_type,
                col(AuditDocument.entity_id) == entity_id,
                col(AuditDocument.changed_at) <= timestamp,
            )
            .order_by(col(AuditDocument.changed_at).desc())
            .limit(1)
        )
        result = await self.session.exec(stmt)
        return result.one_or_none()

    async def list_versions(
        self,
        entity_type: str,
        entity_id: int,
        limit: int = 100,
    ) -> List[AuditDocument]:
        """List all versions for an entity, newest first."""
        stmt = (
            select(AuditDocument)
            .where(
                col(AuditDocument.entity_type) == entity_type,
                col(AuditDocument.entity_id) == entity_id,
            )
            .order_by(col(AuditDocument.version).desc())
            .limit(limit)
        )
        result = await self.session.exec(stmt)
        return list(result.all())

    async def create_version(
        self,
        entity_type: str,
        entity_id: int,
        data_snapshot: Dict,
        change_type: str,
        changed_by: str,
        handler_id: int,
        change_reason: Optional[str] = None,
        ip_address: Optional[str] = None,
        route_path: Optional[str] = None,
        route_payload: Optional[Dict] = None,
        handled_it: Optional[List[str]] = None,
    ) -> AuditDocument:
        """
        Create a new version for an entity.

        Args:
            self.session: Database self.session
            entity_type: Entity table name (e.g., 'factors', 'modules')
            entity_id: Entity primary key
            data_snapshot: Full document snapshot as dict
            change_type: One of 'CREATE', 'UPDATE', 'DELETE', 'ROLLBACK'
            changed_by: User identifier
            handler_id: User ID who performed the action
            change_reason: Optional reason for the change
            ip_address: IP address of the requester (defaults to 'unknown')
            route_path: API route path that triggered the change
            route_payload: Route payload/parameters
            handled_it: List of user provider codes whose data was affected

        Returns:
            The newly created AuditDocument
        """
        # Get current version to compute diff and hash chain
        current = await self.get_current_version(entity_type, entity_id)

        if current:
            new_version = current.version + 1
            previous_hash = current.current_hash
            old_data = current.data_snapshot
        else:
            new_version = 1
            previous_hash = None
            old_data = None

        # Compute diff
        data_diff = self._compute_diff(old_data, data_snapshot)

        # Compute hash
        current_hash = self._compute_hash(
            entity_type, entity_id, new_version, data_snapshot, previous_hash
        )

        # Mark previous version as not current
        if current:
            current.is_current = False
            self.session.add(current)

        # Create new version
        doc_version = AuditDocument(
            entity_type=entity_type,
            entity_id=entity_id,
            version=new_version,
            is_current=True,
            data_snapshot=data_snapshot,
            data_diff=data_diff,
            change_type=change_type,
            change_reason=change_reason,
            changed_by=changed_by,
            changed_at=datetime.now(timezone.utc),
            previous_hash=previous_hash,
            current_hash=current_hash,
            handler_id=str(handler_id),
            handled_it=handled_it or [],
            ip_address=ip_address or "unknown",
            route_path=route_path,
            route_payload=route_payload,
        )

        self.session.add(doc_version)
        await self.session.flush()
        await self.session.refresh(doc_version)

        logger.info(
            f"Created version {new_version} for {entity_type}:{entity_id} "
            f"({change_type}) by {changed_by}"
        )

        return doc_version

    async def rollback_to_version(
        self,
        entity_type: str,
        entity_id: int,
        target_version: int,
        changed_by: str,
        handler_id: int,
        change_reason: Optional[str] = None,
        ip_address: Optional[str] = None,
        route_path: Optional[str] = None,
        route_payload: Optional[Dict] = None,
    ) -> Optional[AuditDocument]:
        """
        Rollback to a previous version by creating a new version with old data.

        This does NOT delete history - it creates a new version with
        change_type='ROLLBACK' containing the data from the target version.

        Returns:
            The new rollback version, or None if target version not found
        """
        # Get the target version
        target = await self.get_version(entity_type, entity_id, target_version)
        if not target:
            logger.warning(
                f"Rollback target version {target_version} not found for "
                f"{entity_type}:{entity_id}"
            )
            return None

        # Create new version with old data
        reason = change_reason or f"Rollback to version {target_version}"
        return await self.create_version(
            entity_type=entity_type,
            entity_id=entity_id,
            data_snapshot=target.data_snapshot,
            change_type="ROLLBACK",
            changed_by=changed_by,
            handler_id=handler_id,
            change_reason=reason,
            ip_address=ip_address,
            route_path=route_path,
            route_payload=route_payload,
        )

    async def verify_hash_chain(self, entity_type: str, entity_id: int) -> bool:
        """
        Verify the hash chain integrity for an entity.

        Returns True if all hashes are valid, False if tampering detected.
        """
        versions = await self.list_versions(entity_type, entity_id, limit=1000)

        # Sort by version ascending
        versions = sorted(versions, key=lambda v: v.version)

        previous_hash: Optional[str] = None
        for version in versions:
            expected_hash = self._compute_hash(
                entity_type,
                entity_id,
                version.version,
                version.data_snapshot,
                version.previous_hash,
            )

            if version.current_hash != expected_hash:
                logger.error(
                    f"Hash mismatch for {entity_type}:{entity_id} v{version.version}"
                )
                return False

            if version.previous_hash != previous_hash:
                logger.error(
                    f"Hash chain broken for {entity_type}:{entity_id} "
                    f"v{version.version}"
                )
                return False

            previous_hash = version.current_hash

        return True

    async def get_factor_snapshot_at_emission(
        self,
        factor_id: int,
        computed_at: datetime,
    ) -> Optional[Dict]:
        """
        Get the factor values as they were when an emission was computed.

        This is the key method for historical traceability - reconstructs
        what inputs were used for a calculation based on document_versions.

        Args:
            self.session: Database self.session
            factor_id: Factor ID
            computed_at: Timestamp when the emission was computed

        Returns:
            Factor data snapshot at that time, or None if not found

        Example:
            ```python
            # Get what factor values were used for this emission
            snapshot = await versioning.get_factor_snapshot_at_emission(
                emission.factor_id, emission.computed_at
            )
            print(snapshot["values"])  # {'active_power_w': 1300, ...}
            ```
        """
        version = await self.get_version_at_time(
            entity_type="factors",
            entity_id=factor_id,
            timestamp=computed_at,
        )
        return version.data_snapshot if version else None

    async def get_emission_factor_snapshot_at_emission(
        self,
        emission_factor_id: int,
        computed_at: datetime,
    ) -> Optional[Dict]:
        """
        Get the emission factor (electricity mix, etc.) as it was when computed.

        Args:
            emission_factor_id: Emission factor ID
            computed_at: Timestamp when the emission was computed

        Returns:
            Emission factor data snapshot at that time, or None if not found
        """
        version = await self.get_version_at_time(
            entity_type="emission_factors",
            entity_id=emission_factor_id,
            timestamp=computed_at,
        )
        return version.data_snapshot if version else None
