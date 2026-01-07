"""Generate Mermaid ER diagram from SQLModel metadata."""

from typing import Optional

from sqlalchemy.orm import DeclarativeMeta
from sqlmodel import SQLModel

# Import all model modules so tables are registered
from app.models import module, module_type, resource, user, variant_type  # noqa: F401


def generate_mermaid(base: Optional[DeclarativeMeta] = None) -> str:
    metadata = base.metadata if base is not None else SQLModel.metadata
    mapper_registry = getattr(base, "registry", None)
    lines = ["```mermaid", "erDiagram"]

    for table_name, table in metadata.tables.items():
        # Table + columns
        lines.append(f"  {table_name} {{")
        for column in table.columns:
            col_type = str(column.type)

            # Determine primary metadata indicator
            # (Mermaid supports only one key per column)
            # Priority: PK > FK > UK (unique) > indexed (shown in comment)
            metadata_key = ""
            comment_parts = []

            if column.primary_key:
                metadata_key = " PK"
                if len(column.foreign_keys) > 0:
                    comment_parts.append("FK")
                if column.index:
                    comment_parts.append("indexed")
            elif len(column.foreign_keys) > 0:
                metadata_key = " FK"
                if column.index:
                    comment_parts.append("indexed")
            elif getattr(column, "unique", False):
                metadata_key = " UK"
                if column.index:
                    comment_parts.append("indexed")
            elif column.index:
                comment_parts.append("indexed")

            # Build comment suffix if additional metadata exists
            comment = f' "{", ".join(comment_parts)}"' if comment_parts else ""
            lines.append(f"    {col_type} {column.name}{metadata_key}{comment}")
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
