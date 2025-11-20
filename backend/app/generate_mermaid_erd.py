from sqlalchemy.orm import DeclarativeMeta

from app.db import Base

# Import all model modules so tables are registered
from app.models import resource, user  # noqa: F401


def generate_mermaid(base: DeclarativeMeta) -> str:
    lines = ["```mermaid", "erDiagram"]

    for table_name, table in base.metadata.tables.items():
        # Table + columns
        lines.append(f"  {table_name} {{")
        for column in table.columns:
            col_type = str(column.type)
            lines.append(f"    {col_type} {column.name}")
        lines.append("  }")

    # Relationships
    for mapper in base.registry.mappers:
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

            # Pick cardinality
            if rel.uselist:
                relation = "||--}o"
            else:
                relation = "||--||"

            lines.append(f"  {parent} {relation} {child} : {rel.key}")
    lines.append("```")
    return "\n".join(lines)


if __name__ == "__main__":
    print("Generating Mermaid ERD...")
    print(generate_mermaid(Base))
    print("Mermaid ERD generation complete.")
"""Generate Mermaid ERD from SQLAlchemy models."""
