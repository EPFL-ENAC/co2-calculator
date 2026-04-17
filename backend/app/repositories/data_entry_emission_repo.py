"""Data entry emission repository for database operations."""

from typing import Any, Dict, List, Optional

from sqlalchemy import ColumnElement, Select, and_, case, literal, or_
from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.constants import ModuleStatus
from app.models.carbon_report import CarbonReport, CarbonReportModule
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_entry_emission import DataEntryEmission, EmissionType
from app.models.factor import Factor
from app.models.module_type import ModuleTypeEnum
from app.utils.it_breakdown import ITSqlTotals


class DataEntryEmissionRepository:
    """Repository for data entry emission database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, obj: DataEntryEmission) -> DataEntryEmission:
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def update(self, obj: DataEntryEmission) -> DataEntryEmission:
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def get_by_data_entry_id(self, data_entry_id: int) -> list[DataEntryEmission]:
        query = select(DataEntryEmission).where(
            DataEntryEmission.data_entry_id == data_entry_id
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def delete_by_data_entry_id(self, data_entry_id: int) -> None:
        query = select(DataEntryEmission).where(
            DataEntryEmission.data_entry_id == data_entry_id
        )
        result = await self.session.execute(query)
        objs = result.scalars().all()
        for obj in objs:
            await self.session.delete(obj)
        if objs:
            await self.session.flush()

    async def bulk_create(
        self, objs: list[DataEntryEmission]
    ) -> list[DataEntryEmission]:
        self.session.add_all(objs)
        await self.session.flush()
        return objs

    async def get_stats(
        self,
        carbon_report_module_id,
        aggregate_by: str = "emission_type_id",
        aggregate_field: str = "kg_co2eq",
    ) -> Dict[str, Optional[float]]:
        """Aggregate DataEntryEmission data by emission_type_id
                SELECT
            dee.*
        FROM
            data_entry_emission dee
        JOIN
            data_entry de ON dee.data_entry_id = de.id
        WHERE
            de.carbon_report_module_id = 'YOUR_REPORT_ID_HERE';
        """
        # 1. Get the model attributes dynamically
        group_field = getattr(DataEntryEmission, aggregate_by)
        sum_field = getattr(DataEntryEmission, aggregate_field)

        # 2. Build the query with the JOIN
        query = (
            select(
                group_field,
                func.sum(sum_field).label("total"),
            )
            .join(DataEntry, col(DataEntryEmission.data_entry_id) == col(DataEntry.id))
            .where(
                DataEntry.carbon_report_module_id == carbon_report_module_id,
            )
            .group_by(group_field)
        )

        result = await self.session.execute(
            query
        )  # Changed .exec to .execute (Standard SQLAlchemy/SQLModel)
        rows = result.all()

        # 3. Format the results
        aggregation: Dict[str, Optional[float]] = {}
        for key, total_count in rows:
            label = str(key) if key is not None else "unknown"
            aggregation[label] = total_count

        return aggregation

    async def get_validated_totals_by_unit(
        self,
        unit_id: int,
    ) -> List[Dict[str, Any]]:
        """Aggregate validated emission totals by year for a unit.

        Joins CarbonReport → CarbonReportModule → DataEntry → DataEntryEmission
        and sums kg_co2eq across ALL validated modules, grouped by year.

        Returns:
            [{"year": 2023, "kg_co2eq": 61700.0}, {"year": 2024, "kg_co2eq": 45000.0}]
        """
        year_expr = col(CarbonReport.year)

        query: Select[Any] = (
            select(
                year_expr.label("year"),
                func.sum(col(DataEntryEmission.kg_co2eq)).label("kg_co2eq"),
            )
            .join(
                DataEntry,
                col(DataEntryEmission.data_entry_id) == col(DataEntry.id),
            )
            .join(
                CarbonReportModule,
                col(DataEntry.carbon_report_module_id) == col(CarbonReportModule.id),
            )
            .join(
                CarbonReport,
                col(CarbonReportModule.carbon_report_id) == col(CarbonReport.id),
            )
            .where(
                CarbonReport.unit_id == unit_id,
                CarbonReportModule.status == ModuleStatus.VALIDATED,
                col(DataEntryEmission.kg_co2eq).isnot(None),
            )
            .group_by(year_expr)
            .order_by(year_expr.asc())
        )

        result = await self.session.execute(query)
        rows = result.all()

        return [
            {
                "year": row.year,
                "kg_co2eq": row.kg_co2eq or None,
            }
            for row in rows
        ]

    async def get_stats_by_carbon_report_id(
        self,
        carbon_report_id: int,
    ) -> Dict[str, float]:
        """Aggregate validated emission totals per module for a carbon report.

        Joins DataEntryEmission → DataEntry → CarbonReportModule and returns
        SUM(kg_co2eq) grouped by module_type_id, filtered to validated modules
        only.

        Returns:
            Dict keyed by module_type_id (as string), e.g.:
            {"2": 15000.0, "4": 41700.0, "7": 5000.0}
        """
        query = (
            select(
                col(CarbonReportModule.module_type_id),
                func.sum(col(DataEntryEmission.kg_co2eq)).label("total"),
            )
            .join(
                DataEntry,
                col(DataEntryEmission.data_entry_id) == col(DataEntry.id),
            )
            .join(
                CarbonReportModule,
                col(DataEntry.carbon_report_module_id) == col(CarbonReportModule.id),
            )
            .where(
                col(CarbonReportModule.carbon_report_id) == carbon_report_id,
                CarbonReportModule.status == ModuleStatus.VALIDATED,
                col(DataEntryEmission.kg_co2eq).isnot(None),
            )
            .group_by(col(CarbonReportModule.module_type_id))
        )

        result = await self.session.execute(query)
        rows = result.all()

        aggregation: Dict[str, float] = {}
        for module_type_id, total in rows:
            label = str(module_type_id) if module_type_id is not None else "unknown"
            aggregation[label] = float(total) if total is not None else 0.0

        return aggregation

    async def get_emission_breakdown(
        self,
        carbon_report_id: int,
    ) -> list[tuple[int, int, float]]:
        """Aggregate emissions by module_type_id and emission_type_id.

        Returns:
            [(module_type_id, emission_type_id, sum_kg_co2eq), ...]
        """
        query = (
            select(
                col(CarbonReportModule.module_type_id),
                col(DataEntryEmission.emission_type_id),
                func.sum(col(DataEntryEmission.kg_co2eq)).label("total"),
            )
            .join(
                DataEntry,
                col(DataEntryEmission.data_entry_id) == col(DataEntry.id),
            )
            .join(
                CarbonReportModule,
                col(DataEntry.carbon_report_module_id) == col(CarbonReportModule.id),
            )
            .where(
                col(CarbonReportModule.carbon_report_id) == carbon_report_id,
                col(DataEntryEmission.kg_co2eq).isnot(None),
            )
            .group_by(
                col(CarbonReportModule.module_type_id),
                col(DataEntryEmission.emission_type_id),
            )
        )

        result = await self.session.execute(query)
        rows = result.all()

        return [
            (
                int(row.module_type_id),
                int(row.emission_type_id),
                float(row.total) if row.total is not None else 0.0,
            )
            for row in rows
        ]

    async def get_emission_breakdown_with_quantity(
        self,
        carbon_report_id: int,
    ) -> list[tuple[int, int, float, float | None]]:
        """Aggregate emissions and quantity by module_type_id and emission_type_id.

        Returns:
            [(module_type_id, emission_type_id, sum_kg_co2eq, sum_quantity), ...]
            where sum_quantity is summed from meta->>'quantity' (NULL when absent).
        """
        query = (
            select(
                col(CarbonReportModule.module_type_id),
                col(DataEntryEmission.emission_type_id),
                func.sum(col(DataEntryEmission.kg_co2eq)).label("total"),
                func.sum(col(DataEntryEmission.meta)["quantity"].as_float()).label(
                    "sum_quantity"
                ),
            )
            .join(
                DataEntry,
                col(DataEntryEmission.data_entry_id) == col(DataEntry.id),
            )
            .join(
                CarbonReportModule,
                col(DataEntry.carbon_report_module_id) == col(CarbonReportModule.id),
            )
            .where(
                col(CarbonReportModule.carbon_report_id) == carbon_report_id,
                col(DataEntryEmission.kg_co2eq).isnot(None),
            )
            .group_by(
                col(CarbonReportModule.module_type_id),
                col(DataEntryEmission.emission_type_id),
            )
        )

        result = await self.session.execute(query)
        rows = result.all()

        return [
            (
                int(row.module_type_id),
                int(row.emission_type_id),
                float(row.total) if row.total is not None else 0.0,
                float(row.sum_quantity) if row.sum_quantity is not None else None,
            )
            for row in rows
        ]

    async def get_it_emission_sql_totals(
        self,
        carbon_report_id: int,
        it_emission_type_ids: list[int],
        validated_source_module_type_ids: list[int],
        exclude_module_type_ids: set[int] | frozenset[int] = frozenset(),
    ) -> ITSqlTotals:
        """Compute IT emission totals via a single SQL query
        using conditional aggregation.

        Four pre-computed totals replace the Python-level aggregation that was
        previously performed inside ``build_it_breakdown``:

        - ``it_total_kg``: sum of IT-typed emissions (excluding excluded modules).
        - ``overall_total_kg``: sum of all emissions (excluding excluded modules).
        - ``validated_source_total_kg``: total emissions from validated IT source
          modules (denominator for ``percentage_of_source_modules``).
        - ``validated_it_kg``: IT emissions from validated IT source modules
          (numerator for ``percentage_of_source_modules``).
        """
        is_it_emission = col(DataEntryEmission.emission_type_id).in_(
            it_emission_type_ids
        )
        is_validated_source = col(CarbonReportModule.module_type_id).in_(
            validated_source_module_type_ids
        )

        base_where: list[ColumnElement[bool]] = [
            col(CarbonReportModule.carbon_report_id) == carbon_report_id,
            col(DataEntryEmission.kg_co2eq).isnot(None),
        ]
        if exclude_module_type_ids:
            base_where.append(
                col(CarbonReportModule.module_type_id).notin_(exclude_module_type_ids)
            )

        query = (
            select(
                func.coalesce(
                    func.sum(
                        case(
                            (is_it_emission, col(DataEntryEmission.kg_co2eq)),
                            else_=None,
                        )
                    ),
                    0.0,
                ).label("it_total_kg"),
                func.coalesce(
                    func.sum(col(DataEntryEmission.kg_co2eq)),
                    0.0,
                ).label("overall_total_kg"),
                func.coalesce(
                    func.sum(
                        case(
                            (is_validated_source, col(DataEntryEmission.kg_co2eq)),
                            else_=None,
                        )
                    ),
                    0.0,
                ).label("validated_source_total_kg"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                and_(is_validated_source, is_it_emission),
                                col(DataEntryEmission.kg_co2eq),
                            ),
                            else_=None,
                        )
                    ),
                    0.0,
                ).label("validated_it_kg"),
            )
            .join(
                DataEntry,
                col(DataEntryEmission.data_entry_id) == col(DataEntry.id),
            )
            .join(
                CarbonReportModule,
                col(DataEntry.carbon_report_module_id) == col(CarbonReportModule.id),
            )
            .where(*base_where)
        )

        result = await self.session.execute(query)
        row = result.one()

        return {
            "it_total_kg": float(row.it_total_kg),
            "overall_total_kg": float(row.overall_total_kg),
            "validated_source_total_kg": float(row.validated_source_total_kg),
            "validated_it_kg": float(row.validated_it_kg),
        }

    async def get_embodied_energy_by_building(
        self,
        carbon_report_id: int,
    ) -> list[tuple[str, float]]:
        """Aggregate embodied-energy emissions per building_name.

        Returns:
            [(building_name, sum_kg_co2eq), ...] sorted by building name.
        """

        building_name_expr = DataEntry.data["building_name"].as_string()
        query: Select[Any] = (
            select(
                building_name_expr.label("building_name"),
                func.sum(col(DataEntryEmission.kg_co2eq)).label("total"),
            )
            .join(
                DataEntry,
                col(DataEntryEmission.data_entry_id) == col(DataEntry.id),
            )
            .join(
                CarbonReportModule,
                col(DataEntry.carbon_report_module_id) == col(CarbonReportModule.id),
            )
            .where(
                col(CarbonReportModule.carbon_report_id) == carbon_report_id,
                col(DataEntry.data_entry_type_id)
                == DataEntryTypeEnum.building_embodied_energy.value,
                col(DataEntryEmission.emission_type_id)
                == EmissionType.buildings__embodied_energy.value,
                col(DataEntryEmission.kg_co2eq).isnot(None),
                building_name_expr.isnot(None),
                building_name_expr != "",
            )
            .group_by(building_name_expr)
            .order_by(building_name_expr)
        )
        result = await self.session.execute(query)
        return [
            (str(row.building_name), float(row.total or 0.0)) for row in result.all()
        ]

    async def get_embodied_energy_by_category(
        self,
        carbon_report_id: int,
    ) -> list[tuple[str, float]]:
        """Aggregate embodied-energy emissions per factor category.

        Aggregates from persisted ``DataEntryEmission`` rows and apportions each
        entry total across factor categories using the factor values that were
        used at compute time (stored in ``meta.factors_used``).

        This keeps the breakdown consistent with:
        - CSV ``kg_co2eq`` overrides (stored emissions may not equal surface × EF)
        - Factor updates after emissions were computed (stored emissions remain
          the source of truth)

        Returns:
            [(category, sum_kg_co2eq), ...] sorted by category.
        """
        query: Select[Any] = (
            select(
                col(DataEntryEmission.kg_co2eq).label("kg_co2eq"),
                col(DataEntryEmission.meta).label("meta"),
            )
            .join(
                DataEntry,
                col(DataEntryEmission.data_entry_id) == col(DataEntry.id),
            )
            .join(
                CarbonReportModule,
                col(DataEntry.carbon_report_module_id) == col(CarbonReportModule.id),
            )
            .where(
                col(CarbonReportModule.carbon_report_id) == carbon_report_id,
                col(DataEntry.data_entry_type_id)
                == DataEntryTypeEnum.building_embodied_energy.value,
                col(DataEntryEmission.emission_type_id)
                == EmissionType.buildings__embodied_energy.value,
                col(DataEntryEmission.kg_co2eq).isnot(None),
                col(DataEntryEmission.kg_co2eq) > 0,
            )
        )

        result = await self.session.execute(query)
        rows = result.all()
        if not rows:
            return []

        def _factor_ids(meta: dict) -> list[int]:
            factors_used = meta.get("factors_used")
            if not isinstance(factors_used, list):
                return []
            ids: list[int] = []
            for f in factors_used:
                if not isinstance(f, dict):
                    continue
                fid = f.get("id")
                if isinstance(fid, int):
                    ids.append(fid)
            return ids

        factor_ids: set[int] = set()
        for row in rows:
            meta = row.meta if isinstance(row.meta, dict) else {}
            factor_ids.update(_factor_ids(meta))

        factor_category_map: dict[int, str] = {}
        factor_ef_map: dict[int, float] = {}
        if factor_ids:
            factor_query: Select[Any] = select(
                col(Factor.id).label("id"),
                Factor.classification["category"].as_string().label("category"),
                Factor.values["ef_kgco2eq_per_m2"].as_float().label("ef"),
            ).where(col(Factor.id).in_(factor_ids))
            factor_result = await self.session.execute(factor_query)
            for f in factor_result.all():
                fid = int(f.id)
                factor_category_map[fid] = str(f.category or "unknown")
                factor_ef_map[fid] = float(f.ef) if f.ef is not None else 0.0

        category_totals: dict[str, float] = {}
        for row in rows:
            kg_total = float(row.kg_co2eq or 0.0)
            if kg_total <= 0:
                continue

            meta = row.meta if isinstance(row.meta, dict) else {}
            surface = meta.get("room_surface_square_meter")
            if surface is None:
                continue
            try:
                surface_f = float(surface)
            except (TypeError, ValueError):
                continue
            if surface_f <= 0:
                continue

            ids = _factor_ids(meta)
            if not ids:
                category_totals["unknown"] = (
                    category_totals.get("unknown", 0.0) + kg_total
                )
                continue

            raw_by_cat: dict[str, float] = {}
            raw_total = 0.0
            for fid in ids:
                ef = factor_ef_map.get(fid, 0.0)
                if ef <= 0:
                    continue
                cat = factor_category_map.get(fid, "unknown")
                raw = surface_f * ef
                raw_by_cat[cat] = raw_by_cat.get(cat, 0.0) + raw
                raw_total += raw

            if raw_total <= 0:
                category_totals["unknown"] = (
                    category_totals.get("unknown", 0.0) + kg_total
                )
                continue

            scale = kg_total / raw_total
            for cat, raw in raw_by_cat.items():
                category_totals[cat] = category_totals.get(cat, 0.0) + (raw * scale)

        return sorted(
            [(cat, total) for cat, total in category_totals.items() if total > 0],
            key=lambda x: x[0],
        )

    async def get_travel_stats_by_class(
        self,
        carbon_report_module_id: int,
    ) -> List[Dict[str, Any]]:
        """
        Aggregate travel emissions by data entry type and cabin_class.
        """
        category_expr = col(DataEntry.data_entry_type_id)
        class_expr = DataEntry.data["cabin_class"].as_string()

        query: Select[Any] = (
            select(
                category_expr.label("category"),
                class_expr.label("class_key"),
                func.sum(col(DataEntryEmission.kg_co2eq)).label("kg_co2eq"),
            )
            .join(
                DataEntry,
                col(DataEntryEmission.data_entry_id) == col(DataEntry.id),
            )
            .where(
                DataEntry.carbon_report_module_id == carbon_report_module_id,
                col(DataEntry.data_entry_type_id).in_(
                    [DataEntryTypeEnum.plane.value, DataEntryTypeEnum.train.value]
                ),
                col(DataEntryEmission.kg_co2eq).isnot(None),
                col(DataEntryEmission.kg_co2eq) > 0,
            )
            .group_by(category_expr, class_expr)
        )

        result = await self.session.execute(query)
        rows = result.all()

        # Group by category, aggregate by class
        data_dict: Dict[str, Dict[str, float]] = {}
        for row in rows:
            if row.category == DataEntryTypeEnum.plane.value:
                category = "plane"
            elif row.category == DataEntryTypeEnum.train.value:
                category = "train"
            else:
                continue
            class_key = row.class_key
            kg_co2eq = float(row.kg_co2eq or 0.0)

            if kg_co2eq <= 0:
                continue

            if category not in data_dict:
                data_dict[category] = {}

            # Default class when null
            if class_key is None:
                if category == "plane":
                    class_key = "eco"
                else:
                    class_key = "class_2"

            data_dict[category][class_key] = (
                data_dict[category].get(class_key, 0.0) + kg_co2eq
            )

        # Build treemap format
        total_kg_co2eq = sum(sum(classes.values()) for classes in data_dict.values())

        result_list: List[Dict[str, Any]] = []
        for category, classes in data_dict.items():
            category_total = sum(classes.values())
            children = []
            for class_key, kg_co2eq in classes.items():
                percentage = (
                    (kg_co2eq / total_kg_co2eq * 100) if total_kg_co2eq > 0 else 0.0
                )
                children.append(
                    {
                        "name": class_key,
                        "value": kg_co2eq,
                        "percentage": percentage,
                    }
                )
            if children and category_total > 0:
                result_list.append(
                    {
                        "name": category,
                        "value": category_total,
                        "children": children,
                    }
                )

        return result_list

    @staticmethod
    def _looks_like_purchase_institutional_code(name: str) -> bool:
        """Return True if ``name`` looks like an institutional code candidate."""
        normalized_name = name.strip()
        if not normalized_name:
            return False
        return normalized_name.lower() not in ("rest", "unknown")

    async def _purchase_code_label_lookup(
        self,
        report_year: int,
        codes_by_det: Dict[int, set[str]],
    ) -> Dict[tuple[int, str], str]:
        """Map (data_entry_type_id, institutional code) → description from factors."""
        result: Dict[tuple[int, str], str] = {}
        code_json = Factor.classification["purchase_institutional_code"].as_string()
        desc_json = Factor.classification[
            "purchase_institutional_description"
        ].as_string()
        for det_id, codes in codes_by_det.items():
            if not codes:
                continue
            stmt = (
                select(code_json, func.max(desc_json))
                .where(
                    col(Factor.data_entry_type_id) == det_id,
                    code_json.in_(sorted(codes)),
                    or_(col(Factor.year) == report_year, col(Factor.year).is_(None)),
                )
                .group_by(code_json)
            )
            exec_result = await self.session.execute(stmt)
            for code, desc in exec_result.all():
                if code and desc:
                    result[(det_id, str(code))] = str(desc)
        return result

    async def get_top_class_breakdown(
        self,
        carbon_report_module_id: int,
        data_entry_types: List[DataEntryTypeEnum],
        group_by_field: str,
        top_n: int = 3,
        label_field: str | None = None,
        report_year: int | None = None,
    ) -> List[Dict[str, Any]]:
        """Aggregate emissions by data entry type and a grouping field.

        Generic method that works for any module. Groups emissions within each
        subcategory (data_entry_type) by the specified JSON data field, returning
        the top N items plus a "rest" bucket.

        Args:
            carbon_report_module_id: The carbon report module to query.
            data_entry_types: Which data entry types to include.
            group_by_field: The DataEntry.data JSON field to group by
                (e.g. ``"equipment_class"`` or
                ``"purchase_institutional_code"``).
            top_n: Number of top items to show per subcategory (default 3).
            label_field: Optional DataEntry.data JSON field to use as the
                display label instead of ``group_by_field`` values
                (e.g. ``"purchase_institutional_description"``).
            report_year: Carbon report year; used to resolve purchase labels from
                ``factors`` when entry rows omit ``purchase_institutional_description``.
        """
        det_name_map = {det.value: det.name for det in data_entry_types}
        category_expr = col(DataEntry.data_entry_type_id)
        class_expr = DataEntry.data[group_by_field].as_string()

        # When a label_field is provided, pick one label per group (MAX)
        has_label = label_field is not None
        label_expr = (
            DataEntry.data[label_field].as_string() if has_label else class_expr
        )

        ranked_columns = [
            category_expr.label("category"),
            func.coalesce(class_expr, literal("unknown")).label("class_key"),
            func.sum(col(DataEntryEmission.kg_co2eq)).label("kg_co2eq"),
            func.row_number()
            .over(
                partition_by=category_expr,
                order_by=func.sum(col(DataEntryEmission.kg_co2eq)).desc(),
            )
            .label("rn"),
        ]
        group_by_columns = [category_expr, class_expr]

        if has_label:
            ranked_columns.append(
                func.max(func.coalesce(label_expr, class_expr)).label("class_label")
            )

        ranked = (
            select(*ranked_columns)
            .join(DataEntry, col(DataEntryEmission.data_entry_id) == col(DataEntry.id))
            .where(
                DataEntry.carbon_report_module_id == carbon_report_module_id,
                col(DataEntry.data_entry_type_id).in_(
                    [det.value for det in data_entry_types]
                ),
                col(DataEntryEmission.kg_co2eq).isnot(None),
                col(DataEntryEmission.kg_co2eq) > 0,
            )
            .group_by(*group_by_columns)
            .cte("ranked")
        )

        bucketed_class = case(
            (ranked.c.rn <= top_n, ranked.c.class_key),
            else_=literal("rest"),
        ).label("class_key")

        outer_columns = [
            ranked.c.category.label("category"),
            bucketed_class,
            func.sum(ranked.c.kg_co2eq).label("kg_co2eq"),
        ]
        group_by_outer = [ranked.c.category, bucketed_class]

        if has_label:
            # For top-N rows: pick the label from the CTE.
            # For "rest" rows: aggregate label doesn't matter, use "rest".
            outer_columns.append(
                func.max(
                    case(
                        (ranked.c.rn <= top_n, ranked.c.class_label),
                        else_=literal("rest"),
                    )
                ).label("class_label")
            )

        query: Select[Any] = select(*outer_columns).group_by(*group_by_outer)

        rows = (await self.session.execute(query)).all()

        data_dict: Dict[int, Dict[str, Any]] = {}
        for row in rows:
            entry = data_dict.setdefault(
                row.category,
                {
                    "name": det_name_map[row.category],
                    "data_entry_type_id": row.category,
                    "value": 0.0,
                    "children": [],
                },
            )
            kg = float(row.kg_co2eq)
            display_name = row.class_label if has_label else row.class_key
            entry["children"].append({"name": display_name, "value": kg})
            entry["value"] += kg

        result_list = list(data_dict.values())
        if (
            has_label
            and label_field == "purchase_institutional_description"
            and report_year is not None
        ):
            codes_by_det: Dict[int, set[str]] = {}
            for group in result_list:
                det_id = group["data_entry_type_id"]
                for child in group["children"]:
                    nm = child["name"]
                    if not isinstance(nm, str):
                        continue
                    if not self._looks_like_purchase_institutional_code(nm):
                        continue
                    codes_by_det.setdefault(det_id, set()).add(nm)
            label_map = await self._purchase_code_label_lookup(
                report_year, codes_by_det
            )
            for group in result_list:
                det_id = group["data_entry_type_id"]
                for child in group["children"]:
                    nm = child["name"]
                    if not isinstance(nm, str):
                        continue
                    if not self._looks_like_purchase_institutional_code(nm):
                        continue
                    resolved = label_map.get((det_id, nm))
                    if resolved:
                        child["name"] = resolved

        for group in result_list:
            group.pop("data_entry_type_id", None)

        return result_list

    async def get_travel_evolution_over_time(
        self,
        unit_id: int,
    ) -> List[Dict[str, Any]]:
        """
        Aggregate travel emissions by year and category across all years
        for a given unit.

        Returns:
        [
            {"year": 2023, "category": "plane", "kg_co2eq": 15000.0},
            {"year": 2023, "category": "train", "kg_co2eq": 8000.0},
            ...
        ]
        """
        year_expr = col(CarbonReport.year)
        category_expr = col(DataEntry.data_entry_type_id)

        query: Select[Any] = (
            select(
                year_expr.label("year"),
                category_expr.label("category"),
                func.sum(col(DataEntryEmission.kg_co2eq)).label("kg_co2eq"),
            )
            .join(
                DataEntry,
                col(DataEntryEmission.data_entry_id) == col(DataEntry.id),
            )
            .join(
                CarbonReportModule,
                col(DataEntry.carbon_report_module_id) == col(CarbonReportModule.id),
            )
            .join(
                CarbonReport,
                col(CarbonReportModule.carbon_report_id) == col(CarbonReport.id),
            )
            .where(
                CarbonReport.unit_id == unit_id,
                CarbonReportModule.module_type_id
                == ModuleTypeEnum.professional_travel.value,
                col(DataEntry.data_entry_type_id).in_(
                    [DataEntryTypeEnum.plane.value, DataEntryTypeEnum.train.value]
                ),
                col(DataEntryEmission.kg_co2eq).isnot(None),
                col(DataEntryEmission.kg_co2eq) > 0,
            )
            .group_by(year_expr, category_expr)
            .order_by(year_expr.asc(), category_expr.asc())
        )

        result = await self.session.execute(query)
        rows = result.all()

        result_list: List[Dict[str, Any]] = []
        for row in rows:
            if row.category == DataEntryTypeEnum.plane.value:
                category = "plane"
            elif row.category == DataEntryTypeEnum.train.value:
                category = "train"
            else:
                continue
            result_list.append(
                {
                    "year": row.year,
                    "category": category,
                    "kg_co2eq": row.kg_co2eq or None,
                }
            )
        return result_list
