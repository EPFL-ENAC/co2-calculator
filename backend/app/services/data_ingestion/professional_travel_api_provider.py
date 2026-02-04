import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from typing import Any, Dict, List, Optional, Set

import requests
from joserfc import jwt as JWT
from joserfc.jwk import OctKey
from sqlmodel import select

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db import SessionLocal
from app.models.data_ingestion import IngestionStatus
from app.models.location import Location
from app.models.user import User
from app.services.data_ingestion.base_provider import DataIngestionProvider
from app.services.professional_travel_service import ProfessionalTravelService

logger = get_logger(__name__)


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
    ):
        super().__init__(config, user)
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
                status_code=IngestionStatus.FAILED,
                extra_metadata={"error": error_message},
            )
            raise

    async def transform_data(
        self, raw_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        try:
            transformed = []

            async def get_location_id_by_code(code: str) -> Optional[int]:
                async with SessionLocal() as db:
                    result = await db.execute(
                        select(Location).where(Location.iata_code == code)
                    )
                    location = result.scalar_one_or_none()
                return location.id if location else None

            for record in raw_data:
                # check date < 01.01.year+1
                departure_date_str = record.get("IN_Departure date") or ""
                departure_date = self._parse_date(departure_date_str)
                if (not departure_date) or (departure_date.year != self.config["year"]):
                    continue  # Skip records not in the target year
                # In your transform_data method, before appending entry:
                origin_code: str = record.get("IN_Segment origin airport code") or ""
                destination_code: str = (
                    record.get("IN_Segment destination airport code") or ""
                )
                origin_location_id = await get_location_id_by_code(origin_code)
                destination_location_id = await get_location_id_by_code(
                    destination_code
                )
                if (origin_location_id is None) or (destination_location_id is None):
                    continue  # Skip records with unknown locations
                sciper = record.get("SCIPER")
                if not sciper or str(sciper).strip() == "":
                    continue  # Skip records without valid sciper

                traveler_name = sciper if sciper else "Unknown"

                entry = {
                    "sciper": sciper,
                    "centre_financier": record.get("Centre financier"),
                    "departure_date": self._parse_date(
                        record.get("IN_Departure date") or ""
                    ),
                    "origin": record.get("IN_Segment origin"),
                    "destination": record.get("IN_Segment destination"),
                    "origin_code": record.get("IN_Segment origin airport code"),
                    "destination_code": record.get(
                        "IN_Segment destination airport code"
                    ),
                    "class_": self._normalize_class(
                        record.get("IN_Segment class") or ""
                    ),
                    "supplier": record.get("IN_Supplier"),
                    "ticket_number": record.get("IN_Ticket number"),
                    "transport_type": record.get("TRANSPORT_TYPE"),
                    "round_trip": record.get("ROUND_TRIP") == "YES",
                    "distance_km": record.get("OUT_DISTANCE_CORRECTED"),
                    "co2_kg": record.get("OUT_CO2_CORRECTED"),
                    "traveler_name": traveler_name,
                    "traveler_id": sciper,
                    "provider": self.config["provider"],
                    "origin_location_id": origin_location_id,
                    "destination_location_id": destination_location_id,
                    "transport_mode": record.get("TRANSPORT_TYPE"),
                    "unit_id": "10208",  # TODO: map from your context or record
                    "year": self.config["year"],
                }
                transformed.append(entry)

            return transformed

        except Exception as e:
            error_message = f"Data transformation failed: {str(e)}"
            logger.error(error_message)
            await self._update_job(
                status_message="failed",
                status_code=IngestionStatus.FAILED,
                extra_metadata={"error": error_message},
            )
            raise

    async def _load_data(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        result = []
        async with SessionLocal() as db:
            professional_travel_service = ProfessionalTravelService(db)
            # data-entries bulk insert
            result = await professional_travel_service.bulk_insert_travel_entries(data)
            # emissions bulk insert
            # professional_travel_emission_service = ProfessionalEmissionService(db)
            # await professional_travel_emission_service.bulk_insert_travel_emissions(
            #     data=Trave
            # )
        return {"inserted": len(result)}

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


def to_bool(value: str) -> bool:
    return value.lower() in ("true", "1", "yes", "on")
