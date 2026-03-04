from pydantic import BaseModel


class TaxonomyNode(BaseModel):
    name: str
    label: str
    children: list["TaxonomyNode"] | None = None
