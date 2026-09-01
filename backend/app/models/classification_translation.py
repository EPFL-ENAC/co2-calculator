"""Translation table for classification labels (#2401).

Backs the ``<field>_<lang>`` CSV convention (e.g. ``equipment_class_fr``):
one row per (field, value, lang) that isn't English. English needs no row —
the untranslated classification value is its own English label (see
``BaseModuleHandler.to_label``).

Year-independent on purpose: labels don't vary by year, unlike the
``factors`` rows they annotate (#2401 issue, proposition 2 vs. wide columns).
"""

from sqlmodel import Field, SQLModel

# The only languages the ingestion/lookup path understands today. A new
# language is a one-line addition here plus a new CSV suffix column — no
# schema change (the whole point of a translation table over wide columns).
TRANSLATABLE_LANGS: tuple[str, ...] = ("fr",)

DEFAULT_LANG = "en"


def normalize_lang(lang: str) -> str:
    """``fr-CH`` -> ``fr``; anything not in ``TRANSLATABLE_LANGS`` -> English.

    English needs no DB lookup at all — the untranslated classification
    value already *is* the English label/search term (#2401). Shared by
    the taxonomy label builder and the submodule search filter so both
    treat the same locale string identically.
    """
    short = lang.split("-")[0].lower()
    return short if short in TRANSLATABLE_LANGS else DEFAULT_LANG


def resolve_label_from_field(
    label_field: str,
    classification: dict,
    value: str,
    translations: dict[tuple[str, str], str],
) -> str:
    """Label for the code + label-field shape: translated → the English
    label text → the bare value; a present-but-blank label field counts as
    absent (real purchase codes ship without a description).

    THE one ladder — the taxonomy builder's kind/subkind branches and the
    table's row labels resolve through here so they can never drift (a
    blank-label 500 was patched twice independently before this existed).
    """
    english = classification.get(label_field)
    if english is None or english == "":
        english = value
    return translations.get((label_field, english), english)


class ClassificationTranslation(SQLModel, table=True):
    """One label for one classification field's value, in one language.

    ``field_name`` is a handler's ``kind_field``/``subkind_field`` (e.g.
    ``"equipment_class"``, ``"sub_class"``) — carried explicitly rather than
    keying on the value alone, since the same string could mean different
    things under different classification fields (#2401 review comment).
    """

    __tablename__ = "classification_translations"

    field_name: str = Field(primary_key=True, max_length=255)
    value: str = Field(primary_key=True, max_length=255)
    lang: str = Field(primary_key=True, max_length=8)
    label: str = Field(nullable=False, max_length=255)
