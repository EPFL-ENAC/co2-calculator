from pydantic import BaseModel


class TaxonomyNode(BaseModel):
    name: str
    label: str
    children: list["TaxonomyNode"] | None = None
    classification: dict[str, float | int | str | None] | None = None
    values: dict[str, float | int | str | None] | None = None
