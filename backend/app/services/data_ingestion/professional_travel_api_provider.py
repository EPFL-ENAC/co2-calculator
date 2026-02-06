import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from typing import Any, Dict, List, Optional, Set

import requests
from joserfc import jwt as JWT
from joserfc.jwk import OctKey

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db import SessionLocal
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_ingestion import IngestionStatus
from app.models.user import User
from app.schemas.data_entry import MODULE_HANDLERS
from app.services.data_entry_service import DataEntryService
from app.services.data_ingestion.base_provider import DataIngestionProvider

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
        """Transform API data using shared handler preprocessing logic."""
        try:
            handler = MODULE_HANDLERS[DataEntryTypeEnum.trips]
            transformed = []

            async with SessionLocal() as db:
                for record in raw_data:
                    # Use handler preprocessing for IATA→location lookup
                    entry = await handler.preprocess_row(  # type: ignore[attr-defined]
                        record, db, self.config
                    )
                    if entry:
                        # Add carbon_report_module_id for DataEntry creation
                        entry["carbon_report_module_id"] = self.config.get(
                            "carbon_report_module_id"
                        )
                        transformed.append(entry)

            logger.info(
                f"Transformed {len(transformed)} records from {len(raw_data)} raw"
            )
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
            service = DataEntryService(db)
            entries = [
                DataEntry(
                    carbon_report_module_id=item.get("carbon_report_module_id"),
                    data_entry_type_id=DataEntryTypeEnum.trips.value,
                    data=item,
                )
                for item in data
            ]
            result = await service.bulk_create(entries)
            await db.commit()
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


def to_bool(value: str) -> bool:
    return value.lower() in ("true", "1", "yes", "on")
