import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from typing import Any, Dict, List, Optional, Set, TypedDict

import requests
from joserfc import jwt as JWT
from joserfc.jwk import OctKey

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.data_entry import DataEntry, DataEntrySourceEnum, DataEntryTypeEnum
from app.models.data_ingestion import IngestionResult, IngestionState
from app.models.user import User
from app.repositories.unit_repo import UnitRepository
from app.schemas.carbon_report import CarbonReportCreate
from app.schemas.user import UserRead
from app.services.carbon_report_service import CarbonReportService
from app.services.data_entry_emission_service import DataEntryEmissionService
from app.services.data_entry_service import DataEntryService
from app.services.data_ingestion.base_provider import DataIngestionProvider

logger = get_logger(__name__)


class StatsDict(TypedDict):
    """Type definition for travel data processing statistics"""

    rows_processed: int
    rows_with_factors: int
    rows_without_factors: int
    rows_skipped: int
    row_errors: list[dict[str, Any]]
    row_errors_count: int


# todo: hard code travel ?
# from app.crud.data_entries import bulk_insert_data_entries
def normalize_vds_payload(payload: Dict[str, Any]) -> tuple[Dict[str, Any], bool]:
    """
    Normalize payload to match VDS schema constraints:
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


class ProfessionalTravelApiProvider(DataIngestionProvider):
    def __init__(
        self,
        config: Dict[str, Any],
        user: User,
        job_session=None,
        *,
        data_session,
    ):
        super().__init__(config, user, job_session, data_session=data_session)
        self.settings = get_settings()
        self.server_url = self.settings.TABLEAU_SERVER_URL
        self.site_content_url = self.settings.TABLEAU_SITE_CONTENT_URL
        self.datasource_luid = self.settings.TABLEAU_DS_FLIGHTS_LUID
        self.client_id = self.settings.TABLEAU_CONNECTED_APP_CLIENT_ID
        self.secret_id = self.settings.TABLEAU_CONNECTED_APP_SECRET_ID
        self.secret_value = self.settings.TABLEAU_CONNECTED_APP_SECRET_VALUE
        self.timeout = int(self.settings.TABLEAU_REQUEST_TIMEOUT_SECONDS)
        self.verify_ssl = to_bool(self.settings.TABLEAU_VERIFY_SSL)
        self.min_api_version = self.settings.TABLEAU_REST_MIN_API_VERSION
        self.max_fields = self.settings.TABLEAU_MAX_FIELDS
        # Extract module_type_id from config for carbon report resolution
        self.module_type_id = config.get("module_type_id")

    async def validate_connection(self) -> bool:
        try:
            jwt_token = self._generate_jwt()
            session = self._create_session()
            x_auth = await self._signin_with_jwt(session, jwt_token)
            return x_auth is not None
        except Exception:
            return False

    async def fetch_data(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        try:
            jwt_token = self._generate_jwt()
            session = self._create_session()
            x_auth = await self._signin_with_jwt(session, jwt_token)

            if x_auth is None:
                raise Exception("Tableau authentication failed")

            metadata = await self._vds_read_metadata(session, x_auth)
            field_captions = self._extract_field_captions(metadata)[: self.max_fields]

            payload = self._build_payload(field_captions)
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

    async def transform_data(
        self, raw_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        try:
            transformed = []

            for record in raw_data:
                # Filter by target year
                # Filter by target year
                departure_date_str = record.get("IN_Departure date") or ""
                departure_date = self._parse_date(departure_date_str)
                if (not departure_date) or (departure_date.year != self.config["year"]):
                    continue

                # Validate SCIPER
                sciper = record.get("SCIPER")
                if not sciper or str(sciper).strip() == "":
                    continue

                # Validate IATA codes
                origin_iata: str = record.get("IN_Segment origin airport code") or ""
                destination_iata: str = (
                    record.get("IN_Segment destination airport code") or ""
                )
                if not origin_iata or not destination_iata:
                    continue

                # Parse number of trips
                raw_trips = record.get("Number of trips")
                try:
                    number_of_trips = int(raw_trips) if raw_trips is not None else 1
                except (ValueError, TypeError):
                    number_of_trips = 1
                number_of_trips = max(1, number_of_trips)
                logger.info(record.get("ROUND_TRIP"))
                unit_institutional_id = record.get("Centre financier") or "unknown_unit"

                # Strip leading character only if it's a prefix (e.g., 'F' in 'F0828')
                # Otherwise use as-is
                def strip_unit_prefix(unit_id: str) -> str:
                    """Strip leading prefix character from unit ID if present."""
                    if not unit_id or unit_id == "unknown_unit":
                        return unit_id
                    # If starts with letter followed by digits, strip the letter
                    if (
                        len(unit_id) > 1
                        and unit_id[0].isalpha()
                        and unit_id[1:].isdigit()
                    ):
                        return unit_id[1:]
                    return unit_id

                entry = {
                    "unit_institutional_id": strip_unit_prefix(unit_institutional_id),
                    "user_institutional_id": sciper,
                    "origin_iata": origin_iata,
                    "destination_iata": destination_iata,
                    "departure_date": (
                        departure_date.isoformat() if departure_date else None
                    ),
                    "number_of_trips": number_of_trips,
                    "cabin_class": self._normalize_class(
                        record.get("IN_Segment class") or ""
                    ),
                    "note": None,
                    # Preserve CO2 and distance from source
                    "co2_kg": record.get("OUT_CO2_CORRECTED"),
                    "distance_km": record.get("OUT_DISTANCE_CORRECTED"),
                    # Keep original values for reference
                    "supplier": record.get("IN_Supplier"),
                    "ticket_number": record.get("IN_Ticket number"),
                    "transport_type": record.get("TRANSPORT_TYPE"),
                    "round_trip": record.get("ROUND_TRIP") == "YES",
                    "passenger_type": record.get("PASSENGER_TYPE"),
                }
                transformed.append(entry)

            return transformed

        except Exception as e:
            error_message = f"Data transformation failed: {str(e)}"
            logger.error(error_message)
            await self._update_job(
                status_message="failed",
                state=IngestionState.FINISHED,
                result=IngestionResult.ERROR,
                state=IngestionState.FINISHED,
                result=IngestionResult.ERROR,
                extra_metadata={"error": error_message},
            )
            raise

    async def ingest(
        self,
        filters: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """
        Override ingest to resolve carbon report modules before loading.

        Matches the pattern from base_csv_provider with stats tracking
        and graceful error handling.
        """
        try:
            await self._update_job(
                status_message="processing",
                state=IngestionState.RUNNING,
                result=None,
                extra_metadata={"message": "Starting travel data processing..."},
            )

            # Fetch data from Tableau API
            raw_data = await self.fetch_data(filters or {})
            await self._update_job(
                status_message="processing",
                state=IngestionState.RUNNING,
                result=None,
                extra_metadata={"message": f"Fetched {len(raw_data)} records"},
            )

            # Transform data (extract and validate fields)
            transformed_data = await self.transform_data(raw_data)
            await self._update_job(
                status_message="processing",
                state=IngestionState.RUNNING,
                result=None,
                extra_metadata={"message": "Resolving carbon report modules..."},
            )

            # Initialize statistics
            max_row_errors = int(self.config.get("max_row_errors", 100))
            stats: StatsDict = {
                "rows_processed": 0,
                "rows_with_factors": 0,
                "rows_without_factors": 0,
                "rows_skipped": 0,
                "row_errors": [],
                "row_errors_count": 0,
            }

            # Resolve carbon report modules
            try:
                unit_to_module_map = await self._resolve_carbon_report_modules(
                    transformed_data
                )
            except ValueError as resolve_error:
                logger.error(f"Carbon report module resolution failed: {resolve_error}")
                await self._update_job(
                    status_message=f"Module resolution failed: {resolve_error}",
                    state=IngestionState.FINISHED,
                    result=IngestionResult.ERROR,
                    extra_metadata={"error": str(resolve_error)},
                )
                raise

            # Inject carbon_report_module_id into each record
            # Skip records with missing/invalid unit_institutional_id
            valid_records = []
            for idx, record in enumerate(transformed_data, start=1):
                unit_code = record.get("unit_institutional_id")
                if not unit_code or str(unit_code).strip() == "":
                    self._record_row_error(
                        stats, idx, "Missing unit_institutional_id", max_row_errors
                    )
                    continue

                unit_code = str(unit_code).strip()
                carbon_report_module_id = unit_to_module_map.get(unit_code)

                if not carbon_report_module_id:
                    self._record_row_error(
                        stats,
                        idx,
                        f"No carbon_report_module_id for unit {unit_code}",
                        max_row_errors,
                    )
                    continue

                record["carbon_report_module_id"] = carbon_report_module_id
                valid_records.append(record)
                stats["rows_processed"] += 1

            if not valid_records:
                error_msg = "No valid records to process after module resolution"
                logger.error(error_msg)
                await self._update_job(
                    status_message=error_msg,
                    state=IngestionState.FINISHED,
                    result=IngestionResult.ERROR,
                    extra_metadata={"error": error_msg, "stats": stats},
                )
                raise ValueError(error_msg)

            # Load data into database
            result = await self._load_data(valid_records)

            # Compute result based on success rate
            if stats["rows_skipped"] == 0:
                ingestion_result = IngestionResult.SUCCESS
            else:
                ingestion_result = IngestionResult.WARNING

            # Update job with summary
            status_message = (
                f"Processed {stats['rows_processed']} records: "
                f"{stats['rows_with_factors']} with factors, "
                f"{stats['rows_without_factors']} without factors, "
                f"{stats['rows_skipped']} skipped"
            )

            # Prepare metadata (exclude row_errors from root to avoid duplication)
            metadata_for_job = {k: v for k, v in stats.items() if k != "row_errors"}
            metadata_for_job["stats"] = stats

            await self._update_job(
                status_message=status_message,
                state=IngestionState.FINISHED,
                result=ingestion_result,
                extra_metadata=metadata_for_job,
            )

            return {
                "state": IngestionState.FINISHED,
                "result": ingestion_result,
                "inserted": result.get("inserted", 0),
                "skipped": stats["rows_skipped"],
                "stats": stats,
            }

        except Exception as e:
            logger.error(f"Travel data ingestion failed: {str(e)}", exc_info=True)
            await self._update_job(
                status_message=f"failed: {str(e)}",
                state=IngestionState.FINISHED,
                result=IngestionResult.ERROR,
                extra_metadata={"error": str(e)},
            )
            raise

    async def _load_data(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Load transformed travel data into database.

        Expects each record to have carbon_report_module_id already resolved.
        Uses self.data_session for consistency.
        Preserves CO2 values from source data (don't recalculate).
        """
        if not data:
            return {"inserted": 0}

        service = DataEntryService(self.data_session)
        emission_service = DataEntryEmissionService(self.data_session)

        # Create data entries with preserved CO2 values
        entries = []
        for item in data:
            carbon_report_module_id = item.get("carbon_report_module_id")
            if not carbon_report_module_id:
                continue

            # Extract CO2 values from item (preserved from source)
            co2_kg = item.get("co2_kg") or item.get("OUT_CO2_CORRECTED")
            distance_km = item.get("distance_km") or item.get("OUT_DISTANCE_CORRECTED")

            # Store in data payload
            data_payload = dict(item)
            if co2_kg is not None:
                data_payload["co2_kg"] = co2_kg
            if distance_km is not None:
                data_payload["distance_km"] = distance_km

            entry = DataEntry(
                carbon_report_module_id=carbon_report_module_id,
                data_entry_type_id=DataEntryTypeEnum.plane.value,
                data=data_payload,
            )
            entries.append(entry)

        if not entries:
            return {"inserted": 0}

        # Bulk create entries
        data_entries_response = await service.bulk_create(
            entries,
            UserRead.model_validate(self.user) if self.user else None,
            job_id=self.job_id,
            source=DataEntrySourceEnum.EXTERNAL_INTEGRATION.value,
            created_by_id=self.job_id,
        )

        # Prepare and create emissions using preserved CO2 values
        emissions_to_create = []
        for data_entry_response in data_entries_response:
            try:
                # Use emission service to prepare emissions
                # This will use the preserved co2_kg from data payload
                emission_objs = await emission_service.prepare_create(
                    data_entry_response
                )
                if emission_objs is not None:
                    emissions_to_create.extend(emission_objs)
            except Exception as emission_error:
                logger.warning(
                    f"Failed to prepare emission for "
                    f"data_entry_id={data_entry_response.id}: "
                    f"{str(emission_error)}"
                )

        if emissions_to_create:
            await emission_service.bulk_create(emissions_to_create)
            logger.info(f"Created {len(emissions_to_create)} emissions")

        # Flush all changes
        await self.data_session.flush()

        return {"inserted": len(data_entries_response)}

    def _generate_jwt(self) -> str:
        key = OctKey.import_key(self.secret_value)
        header = {"alg": "HS256", "kid": self.secret_id}

        now_utc = datetime.now(timezone.utc)
        exp_utc = now_utc + timedelta(minutes=5)

        payload = {
            "iss": self.client_id,
            "sub": self.settings.TABLEAU_USERNAME,
            "aud": "tableau",
            "exp": exp_utc,
            "iat": now_utc,
            "jti": str(uuid.uuid4()),
            "scp": ["tableau:viz_data_service:read"],
        }
        return JWT.encode(header, payload, key)

    async def _signin_with_jwt(
        self, session: requests.Session, jwt_token: str
    ) -> Optional[str]:
        url = f"{self.server_url}/api/{self.min_api_version}/auth/signin"

        payload = {
            "credentials": {
                "jwt": jwt_token,
                "site": {"contentUrl": self.site_content_url},
            }
        }

        response = await asyncio.to_thread(
            session.post, url, json=payload, timeout=self.timeout
        )

        if response.status_code == HTTPStatus.OK:
            return response.json()["credentials"]["token"]

        # Log error details for debugging
        try:
            error_body = response.text
            logger.error(
                f"Tableau sign-in failed status {response.status_code}: {error_body}"
            )
        except Exception as e:
            logger.error(f"Tableau sign-in failed {response.status_code},  {str(e)}")

        return None

    def _create_session(self) -> requests.Session:
        session = requests.Session()
        session.verify = self.verify_ssl
        session.headers.update({"Accept": "application/json"})
        return session

    async def _vds_read_metadata(self, session: requests.Session, x_auth: str) -> Dict:
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

    def _extract_field_captions(self, metadata: Dict) -> List[str]:
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

        out: List[str] = []
        seen: Set[str] = set()

        for f in candidates:
            if not isinstance(f, dict):
                continue
            cap = f.get("fieldCaption")
            if isinstance(cap, str) and cap and cap not in seen:
                out.append(cap)
                seen.add(cap)

        return out

    def _build_payload(self, field_captions: List[str]) -> Dict:
        if not self.datasource_luid:
            raise ValueError("datasource_luid is required")
        if not field_captions:
            raise ValueError("field_captions must contain at least one field")

        payload: Dict[str, Any] = {
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
        self, session: requests.Session, x_auth: str, payload: Dict
    ) -> Dict:
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

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        if not date_str or len(date_str) != 8:
            return None
        return datetime.strptime(date_str, "%Y%m%d")

    def _normalize_class(self, class_str: str) -> str:
        mapping = {
            "AIR ECONOMY CLASS": "eco",
            "AIR BUSINESS CLASS": "business",
            "AIR FIRST CLASS": "first",
        }
        return mapping.get(class_str, "eco")

    async def _resolve_carbon_report_modules(
        self,
        transformed_data: List[Dict[str, Any]],
    ) -> Dict[str, int]:
        """
        Extract unique unit_institutional_ids from travel data
        and resolve carbon_report_module_id.

        Uses 'Centre financier' field (with leading character stripped).

        For each unique unit_institutional_id:
        - Check if carbon report exists for (unit_id, year)
        - Create report if missing (auto-creates all 7 modules)
        - Extract carbon_report_module_id for self.module_type_id

        Args:
            transformed_data: List of transformed travel records

        Returns: {unit_institutional_id: carbon_report_module_id} mapping
        """
        # Validate year is present
        year = self.config.get("year")
        if not year:
            raise ValueError("year is required for travel data import")

        module_type_id = self.module_type_id
        if not module_type_id and self.job and self.job.module_type_id:
            module_type_id = self.job.module_type_id

        if not module_type_id:
            raise ValueError("module_type_id is required for travel data import")

        # Extract unique unit_institutional_ids from transformed data
        unit_codes = set()
        for record in transformed_data:
            unit_code = record.get("unit_institutional_id")
            if unit_code and str(unit_code).strip():
                unit_codes.add(str(unit_code).strip())

        if not unit_codes:
            raise ValueError(
                "No valid unit_institutional_id values found in travel data. "
                "Centre financier column is required."
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

        # Resolve carbon report modules
        carbon_report_service = CarbonReportService(self.data_session)
        code_to_module_map: dict[str, int] = {}
        reports_created = 0
        reports_reused = 0

        for unit_institutional_id in unit_codes:
            # Skip missing units
            unit_id = unit_code_to_id.get(unit_institutional_id)
            if not unit_id:
                logger.warning(
                    "Unit with institutional_id=%s not found, skipping",
                    unit_institutional_id,
                )
                continue

            # Check if carbon report exists
            carbon_report = await carbon_report_service.get_by_unit_and_year(
                unit_id, year
            )

            if not carbon_report:
                # Create new carbon report (auto-creates all 7 modules)
                logger.info(
                    "Creating carbon_report for unit_institutional_id=%s "
                    "(unit_id=%s), year=%s",
                    unit_institutional_id,
                    unit_id,
                    year,
                )
                carbon_report = await carbon_report_service.create(
                    CarbonReportCreate(unit_id=unit_id, year=year)
                )
                reports_created += 1
            else:
                reports_reused += 1

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
            f"Resolved carbon_report_module_ids: "
            f"created {reports_created} new reports, "
            f"reused {reports_reused} existing reports"
        )

        return code_to_module_map

    @staticmethod
    def _record_row_error(
        stats: StatsDict,
        row_idx: int,
        reason: str,
        max_row_errors: int,
    ) -> None:
        """Record a row processing error in stats."""
        stats["rows_skipped"] += 1
        stats["row_errors_count"] += 1
        logger.warning(f"Row {row_idx}: {reason}")
        if len(stats["row_errors"]) < max_row_errors:
            stats["row_errors"].append({"row": row_idx, "reason": reason})


def to_bool(value: str) -> bool:
    return value.lower() in ("true", "1", "yes", "on")
