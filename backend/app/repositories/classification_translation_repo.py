"""Repository for classification label translations (#2401)."""

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.classification_translation import ClassificationTranslation


class ClassificationTranslationRepository:
    """CRUD for ``classification_translations``.

    Volume is small (per-module classification values, not per-year factor
    rows), so a plain VALUES upsert is enough — no COPY staging needed,
    unlike ``FactorRepository.upsert_factors``.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    # Postgres caps one statement at 65,535 bind parameters; at 4 params/row
    # a job-wide flush must chunk (a purchase catalog can collect >16k
    # translations). Same reasoning as FactorRepository._upsert_subset.
    _UPSERT_CHUNK_ROWS = 1000

    async def upsert(self, translations: list[ClassificationTranslation]) -> None:
        """Insert-or-update by the ``(field_name, value, lang)`` PK.

        Idempotent: re-ingesting the same CSV re-upserts identical rows.
        """
        if not translations:
            return
        payload = [t.model_dump() for t in translations]
        for start in range(0, len(payload), self._UPSERT_CHUNK_ROWS):
            chunk = payload[start : start + self._UPSERT_CHUNK_ROWS]
            stmt = pg_insert(ClassificationTranslation).values(chunk)
            stmt = stmt.on_conflict_do_update(
                index_elements=["field_name", "value", "lang"],
                set_={"label": stmt.excluded["label"]},
            )
            await self.session.execute(stmt)

    async def get_labels(
        self,
        field_names: set[str],
        lang: str,
        values: list[str] | None = None,
    ) -> dict[tuple[str, str], str]:
        """``(field_name, value) -> label`` pairs for one language.

        One query per consumer, never per row/node. ``values`` bounds the
        fetch to the caller's own keys — mandatory in spirit for callers
        labeling a page or a typeahead response (purchase's field holds
        ~17k rows); the taxonomy tree builder alone reads a whole field.
        """
        if not field_names or values == []:
            return {}
        conditions = [
            col(ClassificationTranslation.field_name).in_(field_names),
            col(ClassificationTranslation.lang) == lang,
        ]
        if values is not None:
            conditions.append(col(ClassificationTranslation.value).in_(values))
        rows = (
            await self.session.exec(
                select(ClassificationTranslation).where(*conditions)
            )
        ).all()
        return {(row.field_name, row.value): row.label for row in rows}
