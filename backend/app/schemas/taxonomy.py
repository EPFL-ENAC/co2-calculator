from pydantic import BaseModel


class TaxonomyNode(BaseModel):
    name: str
    label: str
    translation_key: str | None = None
    # Display metadata copied from the node's factor row, restricted to the
    # fields its handler whitelists in ``taxonomy_meta_fields`` (#2391). Only
    # what a form or table needs to *render* the option — never an emission
    # coefficient, which #2396 stripped from this payload on purpose. Stays
    # None for handlers that declare nothing so ``response_model_exclude_none``
    # keeps every other module's payload the size it is today.
    meta: dict | None = None
    children: list[TaxonomyNode] | None = None
