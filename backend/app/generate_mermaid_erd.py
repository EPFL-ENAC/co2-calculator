"""Generate Mermaid ER diagram from SQLModel metadata."""

from typing import Optional

from sqlalchemy.orm import DeclarativeMeta
from sqlmodel import SQLModel

# Import all model modules so tables are registered
from app.models import resource, user  # noqa: F401


def generate_mermaid(base: Optional[DeclarativeMeta] = None) -> str:
    metadata = base.metadata if base is not None else SQLModel.metadata
    mapper_registry = getattr(base, "registry", None)
    lines = ["```mermaid", "erDiagram"]

    for table_name, table in metadata.tables.items():
        # Table + columns
        lines.append(f"  {table_name} {{")
        for column in table.columns:
            col_type = str(column.type)
            lines.append(f"    {col_type} {column.name}")
        lines.append("  }")

    # Relationships
    if mapper_registry is not None:
        for mapper in mapper_registry.mappers:
            for rel in mapper.relationships:
                parent = (
                    mapper.local_table.name
                    if hasattr(mapper.local_table, "name")
                    else str(mapper.local_table)
                )
                child = (
                    rel.entity.local_table.name
                    if hasattr(rel.entity.local_table, "name")
                    else str(rel.entity.local_table)
                )

                relation = "||--}o" if rel.uselist else "||--||"
                lines.append(f"  {parent} {relation} {child} : {rel.key}")
    else:
        for table in metadata.tables.values():
            for fk in table.foreign_keys:
                parent = fk.column.table.name
                child = table.name
                relation = "||--}o"
                lines.append(f"  {parent} {relation} {child} : {fk.parent.name}")
    lines.append("```")
    return "\n".join(lines)


if __name__ == "__main__":
    print("Generating Mermaid ERD...")
    print(generate_mermaid())
    print("Mermaid ERD generation complete.")
