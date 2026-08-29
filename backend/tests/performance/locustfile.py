"""Locust load suite for #2295: staged-concurrency tests against a running
backend (local first, dev platform later, ~10x slower DB).

Prerequisites (local):
    make run-db && make perf-seed     # backdrop: units × years × ceiling scale
    make perf-csvs                    # per-module upload CSVs (real factor data)
    cd backend && uv run uvicorn app.main:app --workers 4 --port 8000

Run (see backend/Makefile):
    make perf-load PERF_USERS=50 PERF_CLASSES=ExplorerReadUser
    make perf-sweep                   # the whole 50→1000 / 10→40 ladder

User classes — pass the class names on the CLI to pick a scenario:
    ExplorerReadUser   dashboard/explorer read mix (50/100/200/500/1000)
    ExploreCreateUser  parallel Simulator-Explore report creation (10-40)
    PlanUser           parallel project-plan create → prefill → read → delete
    CsvUploadUser      parallel CSV upload → dispatch → poll to completion

Auth: GET /v1/auth/login-test (DEBUG builds only) sets the auth cookie; on
platforms without it, export PERF_AUTH_COOKIE=<auth_token JWT>. Every
non-GET needs the Sec-Fetch-Site header or RequestOriginMiddleware 403s.
"""

import os
import random
import time
import uuid
from pathlib import Path

from locust import HttpUser, between, task

from app.models.data_entry import DataEntryTypeEnum
from app.models.module_type import MODULE_TYPE_TO_DATA_ENTRY_TYPES, ModuleTypeEnum

ROLE = os.environ.get("PERF_ROLE", "calco2.backoffice.admin")
AUTH_COOKIE = os.environ.get("PERF_AUTH_COOKIE", "")
CSV_DIR = Path(
    os.environ.get(
        "PERF_CSV_DIR", str(Path(__file__).resolve().parents[2] / "INPUT_DATA" / "perf")
    )
)
# How many unit_ids a merged explorer query aggregates over.
MERGED_UNITS = int(os.environ.get("PERF_MERGED_UNITS", "10"))
# Upload/prefill jobs poll every POLL_INTERVAL s until JOB_TIMEOUT s.
JOB_TIMEOUT = float(os.environ.get("PERF_JOB_TIMEOUT", "600"))
POLL_INTERVAL = float(os.environ.get("PERF_POLL_INTERVAL", "2"))

# IngestionState / IngestionResult int values (app/models/data_ingestion.py).
STATE_FINISHED = 3
RESULT_ERROR = 2

CALCULATOR_TYPES_BY_MODULE = {
    module_type: [t for t in types if not t.is_planner_kind]
    for module_type, types in MODULE_TYPE_TO_DATA_ENTRY_TYPES.items()
    if any(not t.is_planner_kind for t in types)
}

# Output names of scripts/generate_perf_test_csvs.py, keyed by ingest type.
CSV_BY_TYPE = {
    DataEntryTypeEnum.member: "perf_headcount_member.csv",
    DataEntryTypeEnum.student: "perf_headcount_student.csv",
    DataEntryTypeEnum.scientific: "perf_equipment_scientific.csv",
    DataEntryTypeEnum.it: "perf_equipment_it.csv",
    DataEntryTypeEnum.other: "perf_equipment_other.csv",
    DataEntryTypeEnum.plane: "perf_travel_planes.csv",
    DataEntryTypeEnum.train: "perf_travel_trains.csv",
    DataEntryTypeEnum.building: "perf_building_rooms.csv",
    DataEntryTypeEnum.energy_combustion: "perf_building_energycombustions.csv",
    DataEntryTypeEnum.external_clouds: "perf_external_clouds.csv",
    DataEntryTypeEnum.external_ai: "perf_external_ai.csv",
    DataEntryTypeEnum.process_emissions: "perf_processemissions.csv",
    DataEntryTypeEnum.scientific_equipment: "perf_purchases_scientific_equipment.csv",
    DataEntryTypeEnum.it_equipment: "perf_purchases_it_equipment.csv",
    DataEntryTypeEnum.consumable_accessories: (
        "perf_purchases_consumable_accessories.csv"
    ),
    DataEntryTypeEnum.biological_chemical_gaseous_product: (
        "perf_purchases_biological_chemical_gaseous_product.csv"
    ),
    DataEntryTypeEnum.services: "perf_purchases_services.csv",
    DataEntryTypeEnum.vehicles: "perf_purchases_vehicles.csv",
    DataEntryTypeEnum.other_purchases: "perf_purchases_other_purchases.csv",
    DataEntryTypeEnum.purchases_centralized: "perf_purchases_centralized.csv",
    DataEntryTypeEnum.research_facilities: "perf_researchfacilities_common.csv",
    DataEntryTypeEnum.animal_facilities: "perf_researchfacilities_animals.csv",
}


def module_of(data_entry_type: DataEntryTypeEnum) -> ModuleTypeEnum:
    for module_type, types in MODULE_TYPE_TO_DATA_ENTRY_TYPES.items():
        if data_entry_type in types:
            return module_type
    raise ValueError(f"{data_entry_type} has no owning module type")


def slug(module_type: ModuleTypeEnum) -> str:
    return module_type.name.replace("_", "-")


class CO2User(HttpUser):
    """Shared login + workspace bootstrap. Not schedulable on its own."""

    abstract = True
    wait_time = between(1, 5)

    def on_start(self):
        # RequestOriginMiddleware rejects cookie-authed non-GETs without a
        # trusted origin marker; Sec-Fetch-Site: none is the sanctioned path.
        self.client.headers.update({"Sec-Fetch-Site": "none"})
        if AUTH_COOKIE:
            self.client.cookies.set("auth_token", AUTH_COOKIE)
        else:
            with self.client.get(
                f"/v1/auth/login-test?role={ROLE}",
                allow_redirects=False,
                name="/v1/auth/login-test",
                catch_response=True,
            ) as resp:
                if resp.status_code != 302:
                    resp.failure(f"login-test returned {resp.status_code}")

        session = self.client.get("/v1/session", name="/v1/session").json()
        self.unit_ids = [u["id"] for u in session.get("units", [])]
        self.years = session.get("configured_years", [])
        if not self.unit_ids:
            # Global-scope roles may carry no unit_users rows; list instead.
            units = self.client.get("/v1/units?limit=1000", name="/v1/units").json()
            self.unit_ids = [u["id"] for u in units]
        if not self.unit_ids or not self.years:
            raise RuntimeError(
                f"no units ({len(self.unit_ids)}) or years ({self.years}) for "
                f"role {ROLE} — is the backdrop seeded (make perf-seed)?"
            )
        self._report_ids: dict[tuple[int, int], int] = {}

    def pick_unit(self) -> int:
        return random.choice(self.unit_ids)  # nosec B311

    def pick_year(self) -> int:
        return random.choice(self.years)  # nosec B311

    def report_id(self, unit_id: int, year: int) -> int | None:
        key = (unit_id, year)
        if key not in self._report_ids:
            resp = self.client.get(
                f"/v1/carbon-reports/unit/{unit_id}/year/{year}/",
                name="/v1/carbon-reports/unit/[id]/year/[y]/",
            )
            if resp.status_code != 200:
                return None
            self._report_ids[key] = resp.json()["id"]
        return self._report_ids[key]

    def fire_flow_metric(self, name: str, start: float, exception=None):
        """Record a multi-request flow's wall time as its own stats row."""
        self.environment.events.request.fire(
            request_type="FLOW",
            name=name,
            response_time=(time.perf_counter() - start) * 1000,
            response_length=0,
            exception=exception,
            context={},
        )


class ExplorerReadUser(CO2User):
    """Dashboard + explorer read mix — the 50/100/200/500/1000 ladder."""

    @task(3)
    def workspace_home(self):
        self.client.get(
            f"/v1/workspace/{self.pick_unit()}/{self.pick_year()}/home",
            name="/v1/workspace/[unit]/[year]/home",
        )

    @task(2)
    def merged_report_stats(self):
        units = random.sample(self.unit_ids, min(MERGED_UNITS, len(self.unit_ids)))  # nosec B311
        self.client.get(
            "/v1/modules-stats/merged/report-stats",
            params={"unit_ids": units, "year": self.pick_year()},
            name="/v1/modules-stats/merged/report-stats",
        )

    @task(1)
    def merged_results_summary(self):
        units = random.sample(self.unit_ids, min(MERGED_UNITS, len(self.unit_ids)))  # nosec B311
        self.client.get(
            "/v1/modules-stats/merged/results-summary",
            params={"unit_ids": units, "year": self.pick_year()},
            name="/v1/modules-stats/merged/results-summary",
        )

    @task(1)
    def merged_multi_year(self):
        units = random.sample(self.unit_ids, min(MERGED_UNITS, len(self.unit_ids)))  # nosec B311
        self.client.get(
            "/v1/modules-stats/merged/multi-year-report-stats",
            params={"unit_ids": units},
            name="/v1/modules-stats/merged/multi-year-report-stats",
        )

    @task(2)
    def unit_totals(self):
        self.client.get(
            f"/v1/unit/{self.pick_unit()}/{self.pick_year()}/totals",
            name="/v1/unit/[id]/[year]/totals",
        )

    @task(1)
    def unit_results(self):
        self.client.get(
            f"/v1/unit/{self.pick_unit()}/results",
            name="/v1/unit/[id]/results",
        )

    @task(2)
    def module_read(self):
        report = self.report_id(self.pick_unit(), self.pick_year())
        if report is None:
            return
        module_type = random.choice(list(CALCULATOR_TYPES_BY_MODULE))  # nosec B311
        self.client.get(
            f"/v1/carbon-reports/{report}/modules/{slug(module_type)}",
            name="/v1/carbon-reports/[id]/modules/[slug]",
        )

    @task(2)
    def submodule_read(self):
        report = self.report_id(self.pick_unit(), self.pick_year())
        if report is None:
            return
        module_type = random.choice(list(CALCULATOR_TYPES_BY_MODULE))  # nosec B311
        entry_type = random.choice(CALCULATOR_TYPES_BY_MODULE[module_type])  # nosec B311
        self.client.get(
            f"/v1/carbon-reports/{report}/modules/{slug(module_type)}/{entry_type.name}",
            params={"page": 1, "limit": 20},
            name="/v1/carbon-reports/[id]/modules/[slug]/[sub]",
        )

    @task(1)
    def explore_read(self):
        self.client.get(
            f"/v1/carbon-reports/simulator/explore/unit/{self.pick_unit()}"
            f"/reference-year/{self.pick_year()}/",
            name="/v1/carbon-reports/simulator/explore/...",
        )


class ExploreCreateUser(CO2User):
    """Parallel Simulator-Explore creation — the 10/20/30/40 ladder."""

    wait_time = between(2, 8)

    @task
    def create_explore(self):
        self.client.post(
            f"/v1/carbon-reports/simulator/explore/unit/{self.pick_unit()}"
            f"/reference-year/{self.pick_year()}/",
            name="POST /v1/carbon-reports/simulator/explore/...",
        )


class PlanUser(CO2User):
    """Full project-plan lifecycle: create → reference year (prefill) →
    read → delete. Wall time of the whole flow lands in the FLOW row.
    """

    wait_time = between(5, 15)

    @task
    def plan_lifecycle(self):
        unit = self.pick_unit()
        start = time.perf_counter()

        created = self.client.post(
            f"/v1/project-plans/unit/{unit}/",
            json={"name": f"perf {uuid.uuid4().hex[:8]}"},
            name="POST /v1/project-plans/unit/[id]/",
        )
        if created.status_code not in (200, 201):
            self.fire_flow_metric(
                "FLOW plan lifecycle", start, Exception("create failed")
            )
            return
        plan_id = created.json()["id"]

        try:
            years = self.client.get(
                f"/v1/project-plans/{plan_id}/years",
                name="/v1/project-plans/[id]/years",
            ).json()
            if not years:
                raise RuntimeError("plan has no year rows")
            plan_year = years[0]["year"]

            patched = self.client.patch(
                f"/v1/project-plans/{plan_id}/years/{plan_year}",
                json={"reference_year": self.pick_year(), "is_grant": False},
                name="PATCH /v1/project-plans/[id]/years/[y]",
            )
            job_id = patched.status_code == 200 and patched.json().get("prefill_job_id")
            if job_id:
                self._poll_prefill(plan_id, job_id)

            self.client.get(
                f"/v1/project-plans/{plan_id}", name="/v1/project-plans/[id]"
            )
            self.client.get(
                f"/v1/project-plans/{plan_id}/aggregate-stats",
                name="/v1/project-plans/[id]/aggregate-stats",
            )
            self.fire_flow_metric("FLOW plan lifecycle", start)
        except Exception as exc:  # noqa: BLE001 — recorded as flow failure
            self.fire_flow_metric("FLOW plan lifecycle", start, exc)
        finally:
            self.client.delete(
                f"/v1/project-plans/{plan_id}",
                name="DELETE /v1/project-plans/[id]",
            )

    def _poll_prefill(self, plan_id: int, job_id) -> None:
        deadline = time.monotonic() + JOB_TIMEOUT
        while time.monotonic() < deadline:
            status = self.client.get(
                f"/v1/project-plans/{plan_id}/prefill/{job_id}",
                name="/v1/project-plans/[id]/prefill/[job]",
            ).json()
            if status.get("finished"):
                return
            time.sleep(POLL_INTERVAL)
        raise TimeoutError(f"prefill {job_id} not finished after {JOB_TIMEOUT}s")


class CsvUploadUser(CO2User):
    """CSV upload → dispatch → poll the ingestion pipeline to completion.
    Wall time of upload-to-ingested lands in the FLOW row.
    """

    wait_time = between(10, 30)

    @task
    def upload_csv(self):
        available = [
            (entry_type, CSV_DIR / name)
            for entry_type, name in CSV_BY_TYPE.items()
            if (CSV_DIR / name).is_file()
        ]
        if not available:
            raise RuntimeError(f"no perf CSVs in {CSV_DIR} — run `make perf-csvs`")
        entry_type, csv_path = random.choice(available)  # nosec B311
        unit, year = self.pick_unit(), self.pick_year()
        module_type = module_of(entry_type)
        start = time.perf_counter()

        try:
            report = self.report_id(unit, year)
            if report is None:
                raise RuntimeError(f"no carbon report for unit {unit} year {year}")
            module = self.client.get(
                f"/v1/carbon-reports/{report}/modules/{slug(module_type)}",
                name="/v1/carbon-reports/[id]/modules/[slug]",
            ).json()
            module_id = module["carbon_report_module_id"]

            with csv_path.open("rb") as handle:
                uploaded = self.client.post(
                    "/v1/files/temp-upload",
                    files={"files": (csv_path.name, handle, "text/csv")},
                    name="POST /v1/files/temp-upload",
                ).json()
            file_path = uploaded[0]["path"]

            with self.client.post(
                "/v1/sync/dispatch",
                json={
                    "ingestion_method": 1,  # csv
                    "target_type": 0,  # data entries
                    "year": year,
                    "filters": {},
                    "file_path": file_path,
                    "config": {
                        "carbon_report_module_id": module_id,
                        "module_type_id": int(module_type),
                        "data_entry_type_id": int(entry_type),
                    },
                },
                name="POST /v1/sync/dispatch",
                catch_response=True,
            ) as dispatched:
                if dispatched.status_code >= 400:
                    dispatched.failure(f"dispatch {dispatched.status_code}")
                    raise RuntimeError(f"dispatch failed: {dispatched.text[:200]}")
                pipeline_id = dispatched.json()["pipeline_id"]

            self._poll_pipeline(pipeline_id)
            self.fire_flow_metric("FLOW csv upload e2e", start)
        except Exception as exc:  # noqa: BLE001 — recorded as flow failure
            self.fire_flow_metric("FLOW csv upload e2e", start, exc)

    def _poll_pipeline(self, pipeline_id) -> None:
        deadline = time.monotonic() + JOB_TIMEOUT
        while time.monotonic() < deadline:
            pipeline = self.client.get(
                f"/v1/sync/pipelines/{pipeline_id}",
                name="/v1/sync/pipelines/[id]",
            ).json()
            jobs = pipeline.get("jobs", [])
            if jobs and all(j.get("state") == STATE_FINISHED for j in jobs):
                failed = [j for j in jobs if j.get("result") == RESULT_ERROR]
                if failed:
                    raise RuntimeError(
                        f"pipeline {pipeline_id}: {len(failed)} job(s) errored"
                    )
                return
            time.sleep(POLL_INTERVAL)
        raise TimeoutError(f"pipeline {pipeline_id} not finished after {JOB_TIMEOUT}s")
