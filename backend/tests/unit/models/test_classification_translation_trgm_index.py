"""#2904 — the label trigram index must live in model code.

It used to exist only in migration ``956c36805397``, so autogenerate kept
proposing to drop it and the #2904 collapse would have silently lost it —
leaving the submodule filter and typeahead ILIKE on a sequential scan.
"""

from app.models.classification_translation import ClassificationTranslation


def test_label_trigram_index_is_declared():
    indexes = {idx.name: idx for idx in ClassificationTranslation.__table__.indexes}
    idx = indexes["ix_classification_translations_label_trgm"]

    assert [c.name for c in idx.columns] == ["label"]
    assert idx.dialect_options["postgresql"]["using"] == "gin"
    assert idx.dialect_options["postgresql"]["ops"] == {"label": "gin_trgm_ops"}
