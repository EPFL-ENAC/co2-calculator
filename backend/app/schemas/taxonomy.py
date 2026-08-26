from pydantic import BaseModel


class TaxonomyNode(BaseModel):
    name: str
    label: str
    translation_key: str | None = None
    children: list[TaxonomyNode] | None = None
