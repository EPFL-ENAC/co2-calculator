"""Base Tableau VDS provider (#1552).

Shared plumbing for Tableau-backed connectors: JWT sign-in, VDS
read-metadata/query, carbon-report-module resolution, and the DB-backed
credential loader. Subclasses supply the connector identity, module type,
required captions, and the module-specific transform/load logic.

Credentials come from the stored ``ConnectorConnection`` +
``ConnectorDatasource`` (form-entered, encrypted at rest) — never from
environment variables. Only the operational knobs (TLS verification,
request timeout, min API version) stay in settings.
"""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from typing import Any, NoReturn, TypedDict

import httpx
from joserfc import jwt as JWT
from joserfc.jwk import OctKey
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.url_safety import validate_external_url
from app.models.connector import ConnectorConnection, ConnectorType
from app.models.data_entry import BULK_PER_YEAR_SOURCES, DataEntryTypeEnum
from app.models.data_ingestion import IngestionResult, IngestionState
from app.models.module_type import ModuleTypeEnum
from app.repositories.unit_repo import UnitRepository
from app.services.carbon_report_service import CarbonReportService
from app.services.connector_service import ConnectorConnectionService
from app.services.data_entry_service import DataEntryService
from app.services.data_ingestion.base_provider import DataIngestionProvider

logger = get_logger(__name__)


class StatsDict(TypedDict):
    """Type definition for travel data processing statistics"""

    rows_processed: int
    rows_with_factors: int
    rows_without_factors: int
    rows_skipped: int
    rows_missing_centre_financier: int
    row_errors: list[dict[str, Any]]
    row_errors_count: int


def normalize_vds_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Normalize payload to match VDS schema constraints:
    - Move query.returnFormat to options.returnFormat
    - Remove query.maxRows
    """
    changed = False
    q = payload.get("query")
    if isinstance(q, dict):
        if "returnFormat" in q:
            rf = q.pop("returnFormat")
            changed = True
            opts = payload.get("options")
            if not isinstance(opts, dict):
                opts = {}
                payload["options"] = opts
            if "returnFormat" not in opts:
                opts["returnFormat"] = rf
        if "maxRows" in q:
            q.pop("maxRows", None)
            changed = True
    return payload, changed


def to_bool(value: str) -> bool:
    return value.lower() in ("true", "1", "yes", "on")


class BaseTableauApiProvider(DataIngestionProvider):
    """DB-backed Tableau VDS provider base.

    Subclasses override the class attrs and implement ``transform_data`` /
    ``_load_data``.
    """

    CONNECTOR: ConnectorType
    MODULE_TYPE: ModuleTypeEnum
    DATA_ENTRY_TYPE: DataEntryTypeEnum
    REQUIRED_CAPTIONS: list[str]

    # Module-specific ingest wording. ``INGEST_NOUN`` drives the progress /
    # failure job messages; ``MISSING_UNIT_REASON`` is the row-error reason
    # for a blank unit code (Centre financier). Never put row contents here —
    # both feed logs and job metadata.
    INGEST_NOUN: str = "data"
    MISSING_UNIT_REASON: str = "Missing unit (Centre financier)"

    @staticmethod
    def _strip_unit_prefix(unit_id: str | None) -> str | None:
        """Strip a single leading letter from unit IDs like 'F0828'."""
        if not unit_id:
            return unit_id
        if len(unit_id) > 1 and unit_id[0].isalpha() and unit_id[1:].isdigit():
            return unit_id[1:]
        return unit_id

    def _bind_connection(
        self, conn: ConnectorConnection, service: ConnectorConnectionService
    ) -> None:
        """Bind a stored connection's fields + operational knobs onto this
        instance. Shared by ``_ensure_credentials`` and ``test_connection``.

        Runs the secret decrypt (Fernet) and the SSRF re-validation, so any
        caller that must tolerate a rotated/corrupt key or a since-tightened
        allowlist has to invoke this inside its own ``try`` — a raw
        ``InvalidToken`` / ``ValueError`` must never escape as an HTTP 500.
        """
        settings = get_settings()
        self.server_url = conn.server_url
        self.site_content_url = conn.site_content_url
        self.username = conn.username
        self.client_id = conn.client_id
        self.secret_id = conn.secret_id
        self.secret_value = service.get_decrypted_secret(conn)
        # SSRF guard on use too (defense in depth): the stored URL may have
        # been written before an allowlist tightening.
        validate_external_url(conn.server_url)
        self.verify_ssl = to_bool(settings.TABLEAU_VERIFY_SSL)  # str-typed setting
        if not self.verify_ssl:
            logger.warning(
                "TLS verification disabled for %s — JWT sent over unverified "
                "TLS; must be enabled in prod.",
                self.CONNECTOR.value,
            )
        self.timeout = int(settings.TABLEAU_REQUEST_TIMEOUT_SECONDS)
        self.min_api_version = settings.TABLEAU_REST_MIN_API_VERSION

    async def _ensure_credentials(self) -> None:
        """Load the connection + per-module datasource from the DB once."""
        if getattr(self, "_credentials_loaded", False):
            return
        service = ConnectorConnectionService(self.data_session)
        conn = await service.get_by_connector(self.CONNECTOR)
        if conn is None:
            raise ValueError(
                f"No {self.CONNECTOR.value} connection configured — set one in "
                "the API connect form before importing."
            )
        ds = await service.datasources.get_active_for_module(
            int(self.MODULE_TYPE), self.config.get("data_entry_type_id")
        )
        if ds is None:
            raise ValueError(
                f"No datasource (LUID) set for module {self.MODULE_TYPE.name} "
                "— set one in the API connect form."
            )
        self._bind_connection(conn, service)
        self.datasource_luid = ds.connector_luid
        self.module_type_id = self.config.get("module_type_id")
        self._credentials_loaded = True

    @classmethod
    async def test_connection(
        cls, db: AsyncSession, connector: ConnectorType
    ) -> tuple[bool, str]:
        """Probe the stored connection with a live JWT sign-in.

        Returns ``(ok, detail)`` where ``detail`` is always a generic,
        operator-safe string — never a raw exception or upstream body.
        """
        service = ConnectorConnectionService(db)
        conn = await service.get_by_connector(connector)
        if conn is None:
            return False, "No connection configured"
        # Throwaway instance bound to the connection fields; no datasource
        # is needed for a sign-in probe. Bind INSIDE the try so a rotated /
        # corrupt secret (Fernet InvalidToken) or since-tightened allowlist
        # returns a generic detail instead of a raw HTTP 500.
        probe = cls({}, None, None, data_session=db)
        try:
            probe._bind_connection(conn, service)
            jwt_token = probe._generate_jwt()
            session = probe._create_session()
            x_auth = await probe._signin_with_jwt(session, jwt_token)
        except Exception:
            logger.error(
                "Connection test failed for %s", connector.value, exc_info=True
            )
            return False, "Connection test failed"
        if x_auth is None:
            return False, "Authentication failed"
        return True, "Connection OK"

    async def validate_connection(self) -> bool:
        try:
            await self._ensure_credentials()
            logger.info(
                "Validating Tableau connection",
                extra={
                    "server_url": self.server_url,
                    "site_content_url": self.site_content_url,
                    "client_id": self.client_id,
                },
            )
            jwt_token = self._generate_jwt()
            logger.debug("JWT token generated successfully")
            session = self._create_session()
            logger.debug("HTTP session created")
            x_auth = await self._signin_with_jwt(session, jwt_token)
            if x_auth is not None:
                logger.info("Tableau connection validated successfully")
                return True
            else:
                logger.error(
                    "Tableau authentication returned None token",
                    extra={"server_url": self.server_url},
                )
                return False
        except ValueError:
            # Config gaps (no connection/datasource, SSRF-blocked host) carry
            # an operator-actionable message — let callers see it rather than
            # collapsing it into a generic False. See data_sync.py's
            # ``except ValueError`` handling around ``validate_connection()``.
            raise
        except Exception as e:
            logger.error(
                "Tableau connection validation failed",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "server_url": self.server_url,
                    "site_content_url": self.site_content_url,
                },
                exc_info=True,
            )
            return False

    async def fetch_data(self, filters: dict[str, Any]) -> list[dict[str, Any]]:
        try:
            await self._ensure_credentials()
            jwt_token = self._generate_jwt()
            session = self._create_session()
            x_auth = await self._signin_with_jwt(session, jwt_token)

            if x_auth is None:
                raise Exception("Tableau authentication failed")

            metadata = await self._vds_read_metadata(session, x_auth)
            available_captions = set(self._extract_field_captions(metadata))
            missing = [c for c in self.REQUIRED_CAPTIONS if c not in available_captions]
            if missing:
                raise ValueError(
                    f"Required Tableau captions missing from datasource "
                    f"metadata: {missing}"
                )
            logger.info(
                "Tableau VDS required captions validated",
                extra={
                    "available_count": len(available_captions),
                    "required_count": len(self.REQUIRED_CAPTIONS),
                    "captions": self.REQUIRED_CAPTIONS,
                },
            )

            payload = self._build_payload(self.REQUIRED_CAPTIONS)
            payload, _ = normalize_vds_payload(payload)
            result = await self._vds_query_datasource(session, x_auth, payload)

            if isinstance(result, dict) and "data" in result:
                return result["data"]
            elif isinstance(result, list):
                return result
            else:
                raise Exception(f"Unexpected VDS response: {result}")
        except Exception as e:
            error_message = f"Data fetch failed: {str(e)}"
            logger.error(error_message)
            await self._update_job(
                status_message="failed",
                state=IngestionState.FINISHED,
                result=IngestionResult.ERROR,
                extra_metadata={"error": error_message},
            )
            raise

    def _generate_jwt(self) -> str:
        logger.debug(
            "Generating JWT token",
            extra={
                "client_id": self.client_id,
                "username": self.username,
                "secret_id": self.secret_id,
            },
        )
        try:
            key = OctKey.import_key(self.secret_value)
            header = {"alg": "HS256", "kid": self.secret_id}

            now_utc = datetime.now(UTC)
            exp_utc = now_utc + timedelta(minutes=5)

            payload = {
                "iss": self.client_id,
                "sub": self.username,
                "aud": "tableau",
                "exp": exp_utc,
                "iat": now_utc,
                "jti": str(uuid.uuid4()),
                "scp": ["tableau:viz_data_service:read"],
            }
            token = JWT.encode(header, payload, key)
            logger.debug("JWT token encoded successfully")
            return token
        except Exception as e:
            logger.error(
                "JWT generation failed",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "client_id": self.client_id,
                },
                exc_info=True,
            )
            raise

    async def _signin_with_jwt(
        self, session: httpx.Client, jwt_token: str
    ) -> str | None:
        url = f"{self.server_url}/api/{self.min_api_version}/auth/signin"

        logger.debug(
            "Attempting Tableau sign-in",
            extra={
                "url": url,
                "site_content_url": self.site_content_url,
                "timeout": self.timeout,
                "verify_ssl": self.verify_ssl,
            },
        )

        payload = {
            "credentials": {
                "jwt": jwt_token,
                "site": {"contentUrl": self.site_content_url},
            }
        }

        try:
            response = await asyncio.to_thread(
                session.post, url, json=payload, timeout=self.timeout
            )

            logger.debug(
                "Tableau sign-in response received",
                extra={
                    "status_code": response.status_code,
                    "url": url,
                },
            )

            if response.status_code == HTTPStatus.OK:
                token = response.json()["credentials"]["token"]
                logger.info("Tableau sign-in successful")
                return token

            # Log error details for debugging
            try:
                error_body = response.text
                logger.error(
                    "Tableau sign-in failed",
                    extra={
                        "status_code": response.status_code,
                        "url": url,
                        "error_body": error_body,
                        "site_content_url": self.site_content_url,
                    },
                )
            except Exception as e:
                logger.error(
                    "Tableau sign-in failed and error body parsing failed",
                    extra={
                        "status_code": response.status_code,
                        "url": url,
                        "parse_error": str(e),
                    },
                )

            return None
        except Exception as e:
            logger.error(
                "Tableau sign-in request failed",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "url": url,
                    "server_url": self.server_url,
                },
                exc_info=True,
            )
            return None

    def _create_session(self) -> httpx.Client:
        logger.debug(
            "Creating HTTP session",
            extra={
                "verify_ssl": self.verify_ssl,
                "timeout": self.timeout,
            },
        )
        session = httpx.Client(
            verify=self.verify_ssl, headers={"Accept": "application/json"}
        )
        logger.debug("HTTP session created successfully")
        return session

    async def _vds_read_metadata(self, session: httpx.Client, x_auth: str) -> dict:
        url = f"{self.server_url}/api/v1/vizql-data-service/read-metadata"
        payload = {"datasource": {"datasourceLuid": self.datasource_luid}}
        headers = {
            "Accept": "application/json",
            "X-Tableau-Auth": x_auth,
        }

        response = await asyncio.to_thread(
            session.post, url, json=payload, headers=headers, timeout=self.timeout
        )

        if response.status_code == HTTPStatus.OK:
            return response.json()
        raise Exception(
            f"Failed to read metadata: {response.status_code} {response.text}"
        )

    def _extract_field_captions(self, metadata: dict) -> list[str]:
        # Try multiple possible locations for fields
        candidates = []

        # Common shapes:
        # - metadata["data"] is a list of field objects
        # - metadata["fields"] is a list of field objects
        if isinstance(metadata.get("data"), list):
            candidates = metadata["data"]
        elif isinstance(metadata.get("fields"), list):
            candidates = metadata["fields"]
        elif isinstance(metadata.get("result"), dict):
            r = metadata["result"]
            if isinstance(r.get("data"), list):
                candidates = r["data"]
            elif isinstance(r.get("fields"), list):
                candidates = r["fields"]

        out: list[str] = []
        seen: set[str] = set()

        for f in candidates:
            if not isinstance(f, dict):
                continue
            cap = f.get("fieldCaption")
            if isinstance(cap, str) and cap and cap not in seen:
                out.append(cap)
                seen.add(cap)

        return out

    def _build_payload(self, field_captions: list[str]) -> dict:
        if not self.datasource_luid:
            raise ValueError("datasource_luid is required")
        if not field_captions:
            raise ValueError("field_captions must contain at least one field")

        payload: dict[str, Any] = {
            "datasource": {"datasourceLuid": self.datasource_luid},
            "query": {
                "fields": [{"fieldCaption": c} for c in field_captions],
            },
            "options": {
                "returnFormat": "OBJECTS",
            },
        }
        return payload

    async def _vds_query_datasource(
        self, session: httpx.Client, x_auth: str, payload: dict
    ) -> dict:
        url = f"{self.server_url}/api/v1/vizql-data-service/query-datasource"
        headers = {
            "Accept": "application/json",
            "X-Tableau-Auth": x_auth,
        }
        response = await asyncio.to_thread(
            session.post, url, json=payload, headers=headers, timeout=self.timeout
        )
        if response.status_code == HTTPStatus.OK:
            return response.json()
        raise Exception(f"Query failed: {response.status_code} {response.text}")

    async def _resolve_carbon_report_modules(
        self,
        transformed_data: list[dict[str, Any]],
    ) -> dict[str, int]:
        """Extract unique unit_institutional_ids from the transformed rows
        and resolve carbon_report_module_id.

        Uses 'Centre financier' field (with leading character stripped).

        For each unique unit_institutional_id:
        - Check if carbon report exists for (unit_id, year)
        - Create report if missing (auto-creates all 7 modules)
        - Extract carbon_report_module_id for self.module_type_id

        Shared by every Tableau-backed provider; user-facing wording is
        parametrized on ``INGEST_NOUN`` so headcount imports don't surface
        travel-specific jargon.

        Args:
            transformed_data: List of transformed records

        Returns: {unit_institutional_id: carbon_report_module_id} mapping
        """
        # Validate year is present
        year = self.config.get("year")
        if not year:
            raise ValueError(f"year is required for {self.INGEST_NOUN} data import")

        module_type_id = self.module_type_id
        if not module_type_id and self.job and self.job.module_type_id:
            module_type_id = self.job.module_type_id

        if not module_type_id:
            raise ValueError(
                f"module_type_id is required for {self.INGEST_NOUN} data import"
            )

        # Extract unique unit_institutional_ids from transformed data
        unit_codes = set()
        for record in transformed_data:
            unit_code = record.get("unit_institutional_id")
            if unit_code and str(unit_code).strip():
                unit_codes.add(str(unit_code).strip())

        if not unit_codes:
            if not transformed_data:
                raise ValueError(
                    f"No {self.INGEST_NOUN} rows passed validation — all rows "
                    "were filtered out during transform. If data is expected, "
                    f"contact the Tableau team that owns the {self.INGEST_NOUN} "
                    "datasource."
                )
            raise ValueError(
                f"No rows could be imported: all {len(transformed_data)} rows "
                "have a null 'Centre financier'. Contact the Tableau team that "
                f"owns the {self.INGEST_NOUN} datasource — the 'Centre "
                "financier' calculated field must be populated for the "
                "requested year."
            )

        logger.info(
            f"Resolving carbon report modules for {len(unit_codes)} unique units: "
            f"{sorted(unit_codes)}"
        )

        # Validate units exist in database
        unit_repo = UnitRepository(self.data_session)
        existing_units = await unit_repo.get_by_institutional_ids(list(unit_codes))
        existing_codes = {unit.institutional_id for unit in existing_units}
        missing_codes = sorted(unit_codes - existing_codes)

        if missing_codes:
            logger.warning(
                f"Found {len(missing_codes)} missing units in database: {missing_codes}"
            )
            # Fail gracefully - don't attempt to fetch from provider

        # Build mapping: institutional_id → unit.id
        unit_code_to_id = {unit.institutional_id: unit.id for unit in existing_units}

        # Resolve carbon report modules (carbon reports are expected to be
        # pre-created by the year-config bootstrap flow).
        carbon_report_service = CarbonReportService(self.data_session)
        code_to_module_map: dict[str, int] = {}

        for unit_institutional_id in unit_codes:
            # Skip missing units
            unit_id = unit_code_to_id.get(unit_institutional_id)
            if not unit_id:
                logger.warning(
                    "Unit with institutional_id=%s not found, skipping",
                    unit_institutional_id,
                )
                continue

            carbon_report = await carbon_report_service.get_by_unit_and_year(
                unit_id, year
            )

            if not carbon_report:
                logger.warning(
                    "No carbon_report for unit_institutional_id=%s "
                    "(unit_id=%s), year=%s — skipping",
                    unit_institutional_id,
                    unit_id,
                    year,
                )
                continue

            # Get the carbon_report_module_id for this module_type
            module_service = carbon_report_service.module_service
            carbon_report_module = await module_service.get_module(
                carbon_report.id, module_type_id
            )

            if not carbon_report_module:
                raise ValueError(
                    f"No carbon_report_module found for "
                    f"carbon_report_id={carbon_report.id}, "
                    f"module_type_id={module_type_id}"
                )

            # Map institutional_id to carbon_report_module_id
            code_to_module_map[unit_institutional_id] = carbon_report_module.id

        logger.info(
            f"Resolved carbon_report_module_ids for {len(code_to_module_map)} units"
        )

        return code_to_module_map

    @staticmethod
    def _record_row_error(
        stats: StatsDict,
        row_idx: int,
        reason: str,
        max_row_errors: int,
        *,
        error_type: str | None = None,
        unit_institutional_id: str | None = None,
    ) -> None:
        """Record a row processing error in stats."""
        stats["rows_skipped"] += 1
        stats["row_errors_count"] += 1
        logger.warning(f"Row {row_idx}: {reason}")
        if len(stats["row_errors"]) < max_row_errors:
            row_error: dict[str, Any] = {"row": row_idx, "reason": reason}
            if error_type is not None:
                row_error["type"] = error_type
            if unit_institutional_id is not None:
                row_error["unit_institutional_id"] = unit_institutional_id
            stats["row_errors"].append(row_error)

    # ------------------------------------------------------------------
    # Shared ingest orchestration (#1552)
    # ------------------------------------------------------------------
    async def ingest(
        self,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Fetch → transform → resolve modules → inject module ids → load.

        Shared across the Tableau-backed providers; subclasses vary only via
        ``transform_data``/``_load_data`` and the module-specific wording
        (``INGEST_NOUN``, ``MISSING_UNIT_REASON``, ``_success_status_message``).
        Progress/failure messages carry counts and unit codes only — never row
        contents (A09: headcount rows are personal data).
        """
        try:
            await self._report_progress(
                f"Starting {self.INGEST_NOUN} data processing..."
            )
            raw_data = await self.fetch_data(filters or {})
            await self._report_progress(f"Fetched {len(raw_data)} records")
            transformed_data = await self.transform_data(raw_data)
            await self._report_progress("Resolving carbon report modules...")
            unit_to_module_map = await self._resolve_modules_or_fail(transformed_data)
            stats = self._init_stats()
            valid_records = self._inject_module_ids(
                transformed_data, unit_to_module_map, stats
            )
            if not valid_records:
                await self._fail_no_valid_records(stats)
            await self._delete_existing_api_entries()
            result = await self._load_data(valid_records)
            return await self._finalize_success(stats, result)
        except Exception as e:
            logger.error(
                f"{self.INGEST_NOUN.capitalize()} data ingestion failed: {str(e)}",
                exc_info=True,
            )
            await self._update_job(
                status_message=f"failed: {str(e)}",
                state=IngestionState.FINISHED,
                result=IngestionResult.ERROR,
                extra_metadata={"error": str(e)},
            )
            raise

    async def _report_progress(self, message: str) -> None:
        """Emit a RUNNING progress heartbeat on the job."""
        await self._update_job(
            status_message="processing",
            state=IngestionState.RUNNING,
            result=None,
            extra_metadata={"message": message},
        )

    async def _resolve_modules_or_fail(
        self, transformed_data: list[dict[str, Any]]
    ) -> dict[str, int]:
        """Resolve modules; on a ValueError mark the job failed then re-raise."""
        try:
            return await self._resolve_carbon_report_modules(transformed_data)
        except ValueError as resolve_error:
            logger.error(f"Carbon report module resolution failed: {resolve_error}")
            await self._update_job(
                status_message=f"Module resolution failed: {resolve_error}",
                state=IngestionState.FINISHED,
                result=IngestionResult.ERROR,
                extra_metadata={"error": str(resolve_error)},
            )
            raise

    @staticmethod
    def _init_stats() -> StatsDict:
        return {
            "rows_processed": 0,
            "rows_with_factors": 0,
            "rows_without_factors": 0,
            "rows_skipped": 0,
            "rows_missing_centre_financier": 0,
            "row_errors": [],
            "row_errors_count": 0,
        }

    def _inject_module_ids(
        self,
        transformed_data: list[dict[str, Any]],
        unit_to_module_map: dict[str, int],
        stats: StatsDict,
    ) -> list[dict[str, Any]]:
        """Attach carbon_report_module_id to each record; skip unresolvable
        units. Row errors carry unit codes only — never member/travel fields.
        """
        max_row_errors = int(self.config.get("max_row_errors", 250))
        valid_records = []
        for idx, record in enumerate(transformed_data, start=1):
            unit_code = str(record.get("unit_institutional_id") or "").strip()
            if not unit_code:
                # Blank Centre financier: a SAP coverage gap (no matching
                # expense report). Tracked separately so a feed regression is
                # detectable from job metadata.
                stats["rows_missing_centre_financier"] += 1
                self._record_row_error(
                    stats, idx, self.MISSING_UNIT_REASON, max_row_errors
                )
                continue
            carbon_report_module_id = unit_to_module_map.get(unit_code)
            if not carbon_report_module_id:
                self._record_row_error(
                    stats,
                    idx,
                    "No unit with unit_institutional_id "
                    f"{unit_code} found after unit sync; no carbon report "
                    "module could be resolved",
                    max_row_errors,
                    error_type="missing_synced_unit",
                    unit_institutional_id=unit_code,
                )
                continue
            record["carbon_report_module_id"] = carbon_report_module_id
            valid_records.append(record)
            stats["rows_processed"] += 1
        return valid_records

    async def _fail_no_valid_records(self, stats: StatsDict) -> NoReturn:
        """Mark the job failed (with stats) and raise — no rows survived."""
        error_msg = "No valid records to process after module resolution"
        logger.error(error_msg)
        await self._update_job(
            status_message=error_msg,
            state=IngestionState.FINISHED,
            result=IngestionResult.ERROR,
            extra_metadata={"error": error_msg, "stats": stats},
        )
        raise ValueError(error_msg)

    async def _delete_existing_api_entries(self) -> int:
        """Replace prior bulk per-year ingests for the target year.

        API feeds are complete yearly exports. Delete every machine-owned
        bulk source (prior API syncs AND per-year CSV uploads — see
        ``BULK_PER_YEAR_SOURCES``) for this provider's data-entry type,
        preserving manual entries and unit-specific uploads. This is called
        only after at least one valid replacement row has survived
        transformation and module resolution.
        """
        year = self.config.get("year")
        if year is None:
            raise ValueError("year is required for API ingestion replacement")

        service = DataEntryService(self.data_session)
        deleted_rows = await service.repo.bulk_delete_by_source_year(
            year=int(year),
            data_entry_type_ids=[self.DATA_ENTRY_TYPE.value],
            sources=[s.value for s in BULK_PER_YEAR_SOURCES],
        )
        logger.info(
            "Deleted %s data entries from the previous %s bulk ingest "
            "(year=%s, data_entry_type_id=%s)",
            deleted_rows,
            self.INGEST_NOUN,
            year,
            self.DATA_ENTRY_TYPE.value,
        )
        return deleted_rows

    async def _finalize_success(
        self, stats: StatsDict, result: dict[str, Any]
    ) -> dict[str, Any]:
        ingestion_result = IngestionResult.SUCCESS
        if stats["rows_skipped"]:
            ingestion_result = IngestionResult.WARNING
        metadata_for_job = {k: v for k, v in stats.items() if k != "row_errors"}
        metadata_for_job["stats"] = stats
        await self._update_job(
            status_message=self._success_status_message(stats),
            state=IngestionState.FINISHED,
            result=ingestion_result,
            extra_metadata=metadata_for_job,
        )
        return {
            "state": IngestionState.FINISHED,
            "result": ingestion_result,
            "status_message": self._success_status_message(stats),
            "inserted": result.get("inserted", 0),
            "skipped": stats["rows_skipped"],
            "stats": stats,
        }

    def _success_status_message(self, stats: StatsDict) -> str:
        """Module-specific success summary. Overridden per provider."""
        return (
            f"Processed {stats['rows_processed']} records, "
            f"{stats['rows_skipped']} skipped"
        )
