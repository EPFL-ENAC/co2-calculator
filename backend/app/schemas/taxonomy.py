from pydantic import BaseModel


class TaxonomyNode(BaseModel):
    name: str
    label: str
    translation_key: str | None = None
    children: list["TaxonomyNode"] | None = None
    classification: dict[str, float | int | str | None] | None = None
    values: dict[str, float | int | str | None] | None = None
