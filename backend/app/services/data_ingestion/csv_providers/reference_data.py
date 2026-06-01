"""Reference-data CSV provider.

Dispatches by ``data_entry_type_id``:

- ``train`` (21) → upsert into ``locations`` table (train rows only)
- ``plane`` (20) → upsert into ``locations`` table (plane rows only)
- ``building`` (30) → delete + insert into ``building_rooms`` table

Reference data is **year-agnostic** by design: rows write to the global
``locations`` / ``building_rooms`` tables with no ``year`` column.  The
job row still carries ``year`` so the dashboard can show "last uploaded
under year X", but the data itself is shared across every report year.

Locations use the same staging-table + COPY + UPSERT path as
``app.seed.seed_locations`` (``_NATURAL_KEY_EXPR`` stays in lock-step with
``Location.compute_natural_key`` so seed and ingest dedupe identically).
Building rooms follow the seed's full-replacement semantics
(``delete(BuildingRoom)`` then re-insert) — uploading a partial CSV
clears the rest of the table.
"""

import csv
import io
import urllib.parse
from typing import Any, Dict, List

import psycopg
from sqlalchemy.engine.url import make_url
from sqlmodel import delete

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.building_room import BuildingRoom
from app.models.data_entry import DataEntryTypeEnum
from app.models.data_ingestion import (
    EntityType,
    IngestionMethod,
    IngestionResult,
    IngestionState,
    TargetType,
)
from app.models.user import User
from app.seed.seed_locations import _NATURAL_KEY_EXPR
from app.services.data_ingestion.base_csv_provider import _validate_file_path
from app.services.data_ingestion.base_provider import DataIngestionProvider

logger = get_logger(__name__)


LOCATIONS_REQUIRED_COLUMNS = {
    "transport_mode",
    "name",
    "latitude",
    "longitude",
}
LOCATIONS_EXPECTED_COLUMNS = LOCATIONS_REQUIRED_COLUMNS | {
    "airport_size",
    "continent",
    "country_code",
    "municipality",
    "iata_code",
    "keywords",
}

BUILDING_ROOMS_REQUIRED_COLUMNS = {
    "building_location",
    "building_name",
    "room_name",
}
BUILDING_ROOMS_EXPECTED_COLUMNS = BUILDING_ROOMS_REQUIRED_COLUMNS | {
    "room_type",
    "room_surface_square_meter",
}


class ReferenceDataCSVProvider(DataIngestionProvider):
    """CSV provider for reference data (locations, building rooms).

    Routed by ``(module_type_id, csv, REFERENCE_DATA, MODULE_PER_YEAR)``;
    inside the provider, dispatch by ``data_entry_type_id``.
    """

    def __init__(
        self,
        config: Dict[str, Any],
        user: User | None = None,
        job_session: Any = None,
        data_session: Any = None,
    ) -> None:
        super().__init__(config, user, job_session, data_session=data_session)
        self.job_id = config.get("job_id")
        self.module_type_id = config.get("module_type_id")
        self.data_entry_type_id = config.get("data_entry_type_id")
        raw_file_path = config.get("file_path")
        self.source_file_path = (
            urllib.parse.unquote(raw_file_path) if raw_file_path else None
        )
        if self.source_file_path:
            _validate_file_path(self.source_file_path)
        self._files_store: Any = None
        logger.info(
            f"Initializing {self.__class__.__name__} for job_id={self.job_id}, "
            f"file_path={self.source_file_path}, "
            f"data_entry_type_id={self.data_entry_type_id}"
        )

    @property
    def provider_name(self) -> IngestionMethod:
        return IngestionMethod.csv

    @property
    def target_type(self) -> TargetType:
        return TargetType.REFERENCE_DATA

    @property
    def entity_type(self) -> EntityType:
        return EntityType.MODULE_PER_YEAR

    @property
    def files_store(self) -> Any:
        if self._files_store is None:
            from app.api.v1.files import make_files_store

            self._files_store = make_files_store()
        return self._files_store

    async def validate_connection(self) -> bool:
        if not self.source_file_path:
            logger.warning("No file_path provided in config")
            return False
        try:
            return await self.files_store.file_exists(self.source_file_path)
        except Exception as exc:
            logger.error(f"Failed to validate reference CSV: {exc}")
            return False

    async def fetch_data(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        return []

    async def transform_data(
        self, raw_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        return raw_data

    async def _load_data(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {"inserted": 0, "skipped": 0, "errors": 0}

    async def ingest(self, filters: Dict[str, Any] | None = None) -> Dict[str, Any]:
        try:
            await self._update_job(
                status_message="processing",
                state=IngestionState.RUNNING,
                result=None,
                extra_metadata={"message": "Starting reference CSV processing..."},
            )

            det = self._resolve_data_entry_type()
            csv_text, processing_path, filename = await self._stage_file()

            if det in (DataEntryTypeEnum.plane, DataEntryTypeEnum.train):
                stats = await self._ingest_locations(csv_text, det)
            elif det == DataEntryTypeEnum.building:
                stats = await self._ingest_building_rooms(csv_text)
            else:
                raise ValueError(
                    f"data_entry_type_id={det.value} is not a supported "
                    "reference type (expected plane=20, train=21, building=30)"
                )

            processed_path = await self._move_to_processed(processing_path, filename)

            result = (
                IngestionResult.SUCCESS
                if stats["rows_skipped"] == 0 and stats["rows_processed"] > 0
                else IngestionResult.WARNING
                if stats["rows_processed"] > 0
                else IngestionResult.ERROR
            )
            status_message = (
                f"Processed {stats['rows_processed']} rows: "
                f"{stats['rows_skipped']} skipped, "
                f"{stats['rows_inserted']} inserted"
            )
            await self._update_job(
                status_message=status_message,
                state=IngestionState.FINISHED,
                result=result,
                extra_metadata={
                    **stats,
                    "stats": stats,
                    "processed_file_path": processed_path,
                    "filename": filename,
                },
            )
            return {
                "state": IngestionState.FINISHED,
                "status_message": status_message,
                "data": {
                    "result": result,
                    "inserted": stats["rows_inserted"],
                    "skipped": stats["rows_skipped"],
                    "stats": stats,
                },
            }
        except Exception as exc:
            await self._update_job(
                status_message=f"failed: {exc}",
                state=IngestionState.FINISHED,
                result=IngestionResult.ERROR,
                extra_metadata={"error": str(exc)},
            )
            logger.exception("Reference CSV ingestion failed")
            raise

    def _resolve_data_entry_type(self) -> DataEntryTypeEnum:
        if self.data_entry_type_id is None:
            raise ValueError(
                "data_entry_type_id is required for reference data ingestion"
            )
        return DataEntryTypeEnum(int(self.data_entry_type_id))

    async def _stage_file(self) -> tuple[str, str, str]:
        """Move the uploaded file from tmp/ → processing/ and read its bytes."""
        if not self.source_file_path:
            raise ValueError("Missing file_path in config")
        _validate_file_path(self.source_file_path)
        filename = self.source_file_path.split("/")[-1]
        processing_path = f"processing/{self.job_id}/{filename}"
        logger.info(f"Moving file from {self.source_file_path} to {processing_path}")
        move_result = await self.files_store.move_file(
            self.source_file_path, processing_path
        )
        if not move_result:
            raise ValueError("Failed to move file to processing path")

        file_content, _ = await self.files_store.get_file(processing_path)
        csv_text = file_content.decode("utf-8")
        return csv_text, processing_path, filename

    async def _move_to_processed(self, processing_path: str, filename: str) -> str:
        """On success only — promote ``processing/<job>/<file>`` to ``processed/``.

        Kept off the failure path so an admin downloading "the last CSV"
        always reads a file that was actually ingested.
        """
        processed_path = f"processed/{self.job_id}/{filename}"
        moved = await self.files_store.move_file(processing_path, processed_path)
        if not moved:
            logger.warning(
                f"Failed to move {processing_path} to {processed_path} — "
                "keeping in processing/"
            )
            return processing_path
        return processed_path

    @staticmethod
    def _validate_headers(
        csv_text: str,
        required_columns: set[str],
        expected_columns: set[str],
    ) -> None:
        reader = csv.DictReader(io.StringIO(csv_text))
        try:
            first = next(reader)
        except StopIteration:
            raise ValueError("CSV file is empty")
        keys = set(first.keys())
        missing_required = required_columns - keys
        if missing_required:
            raise ValueError(
                "CSV is missing required columns: "
                f"{', '.join(sorted(missing_required))}"
            )
        unknown = keys - expected_columns
        if unknown:
            logger.warning(
                f"Reference CSV has unexpected columns (ignored): "
                f"{', '.join(sorted(unknown))}"
            )

    async def _ingest_locations(
        self, csv_text: str, det: DataEntryTypeEnum
    ) -> Dict[str, Any]:
        """COPY into a staging temp table, then REPLACE the ``locations`` of
        this upload's mode.

        Mirrors the seed-time path in ``app.seed.seed_locations`` — same
        natural-key expression, same staging columns. Rows are filtered to
        ``transport_mode = {det.name}`` so a "plane" CSV that accidentally
        contains train rows (or vice-versa) does not pollute the table.

        Replace is scoped per mode: the prior train (or plane) rows are
        deleted inside the same transaction before re-insert, so a reupload
        from a new source does not accumulate stale stations. Plane rows are
        untouched by a train upload and vice-versa. (Building rooms replace
        the same way — see ``_ingest_building_rooms``.)
        """
        self._validate_headers(
            csv_text, LOCATIONS_REQUIRED_COLUMNS, LOCATIONS_EXPECTED_COLUMNS
        )

        rows = self._parse_locations_rows(csv_text, det)
        if not rows:
            return {
                "rows_processed": 0,
                "rows_skipped": 0,
                "rows_inserted": 0,
            }

        settings = get_settings()
        if not settings.DB_URL:
            raise ValueError("DB_URL is not configured")
        url = make_url(settings.DB_URL)
        if url.drivername.split("+")[0] != "postgresql":
            return await self._ingest_locations_sqlite(rows, det)

        conn_kwargs: Dict[str, Any] = {
            "host": url.host,
            "port": url.port or 5432,
            "dbname": url.database,
        }
        if url.username:
            conn_kwargs["user"] = url.username
        if url.password:
            conn_kwargs["password"] = url.password

        copy_sql = (
            "COPY locations_staging ("
            "transport_mode, airport_size, name, latitude, longitude, "
            "continent, country_code, municipality, iata_code, keywords"
            ") FROM STDIN CSV NULL ''"
        )
        upsert_sql = f"""
            INSERT INTO locations (
                transport_mode, airport_size, name, latitude, longitude,
                continent, country_code, municipality, iata_code, keywords,
                natural_key
            )
            SELECT DISTINCT ON (nk)
                transport_mode::transportmodeenum, airport_size, name,
                latitude::float, longitude::float,
                continent, country_code, municipality, iata_code, keywords,
                nk AS natural_key
            FROM (
                SELECT *,
                    {_NATURAL_KEY_EXPR} AS nk
                FROM locations_staging
            ) deduped
            ORDER BY nk
            ON CONFLICT (natural_key) DO UPDATE SET
                name         = EXCLUDED.name,
                latitude     = EXCLUDED.latitude,
                longitude    = EXCLUDED.longitude,
                country_code = EXCLUDED.country_code,
                iata_code    = EXCLUDED.iata_code,
                airport_size = EXCLUDED.airport_size,
                continent    = EXCLUDED.continent,
                municipality = EXCLUDED.municipality,
                keywords     = EXCLUDED.keywords,
                natural_key  = EXCLUDED.natural_key
        """  # nosec B608 - constants only, no user input

        rows_inserted = 0
        async with await psycopg.AsyncConnection.connect(**conn_kwargs) as conn:
            await conn.execute(
                """
                CREATE TEMP TABLE locations_staging (
                    transport_mode TEXT, airport_size TEXT, name TEXT,
                    latitude FLOAT, longitude FLOAT, continent TEXT,
                    country_code TEXT, municipality TEXT, iata_code TEXT, keywords TEXT
                ) ON COMMIT DROP
                """
            )
            async with conn.cursor() as cur:
                async with cur.copy(copy_sql) as copy:
                    buf = io.StringIO()
                    writer = csv.writer(buf)
                    for row in rows:
                        writer.writerow(row)
                    await copy.write(buf.getvalue().encode("utf-8"))
                # Replace, scoped to this upload's mode: erase the prior
                # train (or plane) reference inside the same transaction so a
                # reupload from a new source does not accumulate stale
                # stations. The COPY above already filtered rows to det.name.
                await cur.execute(
                    "DELETE FROM locations "
                    "WHERE transport_mode = %s::transportmodeenum",
                    (det.name,),
                )
                await cur.execute(upsert_sql)
                rows_inserted = cur.rowcount if cur.rowcount >= 0 else len(rows)
            await conn.commit()

        return {
            "rows_processed": len(rows),
            "rows_skipped": 0,
            "rows_inserted": rows_inserted,
        }

    @staticmethod
    def _parse_locations_rows(csv_text: str, det: DataEntryTypeEnum) -> List[List[str]]:
        target_mode = det.name  # "plane" or "train"
        rows: List[List[str]] = []
        reader = csv.DictReader(io.StringIO(csv_text))
        for raw in reader:
            mode = (raw.get("transport_mode") or "").strip().lower()
            if mode != target_mode:
                continue
            rows.append(
                [
                    mode,
                    (raw.get("airport_size") or "").strip(),
                    (raw.get("name") or "").strip(),
                    (raw.get("latitude") or "").strip(),
                    (raw.get("longitude") or "").strip(),
                    (raw.get("continent") or "").strip(),
                    (raw.get("country_code") or "").strip(),
                    (raw.get("municipality") or "").strip(),
                    (raw.get("iata_code") or "").strip(),
                    (raw.get("keywords") or "").strip(),
                ]
            )
        return rows

    async def _ingest_locations_sqlite(
        self, rows: List[List[str]], det: DataEntryTypeEnum
    ) -> Dict[str, Any]:
        """SQLite fallback for tests: ORM upsert keyed on natural_key.

        Production runs against PostgreSQL via the COPY+UPSERT path above;
        this branch exists so the test suite (SQLite) can exercise the
        provider without a Postgres-only ``transportmodeenum`` cast.
        """
        from sqlalchemy import select

        from app.models.location import Location, TransportModeEnum

        # Replace, scoped to this upload's mode: erase the prior train (or
        # plane) reference before re-inserting, so a reupload from a new
        # source does not accumulate stale stations. Plane rows are left
        # untouched by a train upload and vice-versa.
        target_mode = TransportModeEnum(det.name)
        await self.data_session.exec(
            delete(Location).where(
                Location.transport_mode == target_mode  # type: ignore[arg-type]
            )
        )

        inserted = 0
        for row in rows:
            (
                mode,
                airport_size,
                name,
                lat,
                lon,
                continent,
                country_code,
                municipality,
                iata_code,
                keywords,
            ) = row
            try:
                latitude = float(lat)
                longitude = float(lon)
            except ValueError:
                continue
            transport_mode = TransportModeEnum(mode)
            natural_key = Location.compute_natural_key(
                transport_mode=transport_mode,
                name=name,
                latitude=latitude,
                longitude=longitude,
                country_code=country_code or None,
                iata_code=iata_code or None,
            )
            # mypy without the SQLAlchemy plugin sees ``Column == value`` as
            # ``bool``; at runtime it's a ``BinaryExpression``.  Same workaround
            # used elsewhere in the codebase (see app/api/v1/data_sync.py).
            existing = await self.data_session.execute(
                select(Location).where(
                    Location.natural_key == natural_key  # type: ignore[arg-type]
                )
            )
            row_obj = existing.scalar_one_or_none()
            if row_obj is None:
                row_obj = Location(
                    transport_mode=transport_mode,
                    airport_size=airport_size or None,
                    name=name,
                    latitude=latitude,
                    longitude=longitude,
                    continent=continent or None,
                    country_code=country_code or None,
                    municipality=municipality or None,
                    iata_code=iata_code or None,
                    keywords=keywords or None,
                    natural_key=natural_key,
                )
                self.data_session.add(row_obj)
            else:
                row_obj.airport_size = airport_size or None
                row_obj.name = name
                row_obj.latitude = latitude
                row_obj.longitude = longitude
                row_obj.continent = continent or None
                row_obj.country_code = country_code or None
                row_obj.municipality = municipality or None
                row_obj.iata_code = iata_code or None
                row_obj.keywords = keywords or None
                self.data_session.add(row_obj)
            inserted += 1
        await self.data_session.flush()
        return {
            "rows_processed": len(rows),
            "rows_skipped": 0,
            "rows_inserted": inserted,
        }

    async def _ingest_building_rooms(self, csv_text: str) -> Dict[str, Any]:
        """Delete and re-insert all building rooms (matches seed semantics).

        Uploading a partial CSV will wipe everything outside it; the
        FE makes this explicit to the admin.
        """
        self._validate_headers(
            csv_text,
            BUILDING_ROOMS_REQUIRED_COLUMNS,
            BUILDING_ROOMS_EXPECTED_COLUMNS,
        )

        rooms: List[BuildingRoom] = []
        skipped = 0
        reader = csv.DictReader(io.StringIO(csv_text))
        for raw in reader:
            building_location = (raw.get("building_location") or "").strip()
            building_name = (raw.get("building_name") or "").strip()
            room_name = (raw.get("room_name") or "").strip()
            if not (building_location and building_name and room_name):
                skipped += 1
                continue
            rooms.append(
                BuildingRoom(
                    building_location=building_location,
                    building_name=building_name,
                    room_name=room_name,
                    room_type=(raw.get("room_type") or "").strip() or None,
                    room_surface_square_meter=_to_float(
                        raw.get("room_surface_square_meter")
                    ),
                )
            )

        await self.data_session.exec(delete(BuildingRoom))
        if rooms:
            self.data_session.add_all(rooms)
        await self.data_session.flush()

        return {
            "rows_processed": len(rooms),
            "rows_skipped": skipped,
            "rows_inserted": len(rooms),
        }


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized or normalized == "-":
        return None
    try:
        return float(normalized)
    except ValueError:
        return None
