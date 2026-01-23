"""Generate Mermaid ER diagram from SQLModel metadata."""

from typing import Optional

from sqlalchemy.orm import DeclarativeMeta
from sqlmodel import SQLModel

# Import all model modules so tables are registered
import app.models  # noqa: F401


def generate_mermaid(base: Optional[DeclarativeMeta] = None) -> str:
    metadata = base.metadata if base is not None else SQLModel.metadata
    mapper_registry = getattr(base, "registry", None)
    lines = ["```mermaid", "erDiagram"]

    # Sort tables for consistency
    for table_name, table in sorted(metadata.tables.items()):
        lines.append(f"  {table_name} {{")
        # Sort columns by name
        sorted_columns = sorted(table.columns, key=lambda c: c.name)
        for column in sorted_columns:
            # Clean types (e.g., VARCHAR(255) -> VARCHAR) to avoid Mermaid syntax errors
            col_type = str(column.type).split("(")[0].replace(" ", "_")
            col_name = column.name

            metadata_key = ""
            if column.primary_key:
                metadata_key = " PK"
            elif len(column.foreign_keys) > 0:
                metadata_key = " FK"

            # Add "indexed" if the column is indexed (excluding PK/FK)
            is_indexed = any(
                col.name == column.name for idx in table.indexes for col in idx.columns
            )
            if is_indexed and not column.primary_key and len(column.foreign_keys) == 0:
                metadata_key += ' "indexed"'

            lines.append(f"    {col_type} {col_name}{metadata_key}")
        lines.append("  }")

    relationship_lines = []
    if mapper_registry is not None:
        for mapper in mapper_registry.mappers:
            for rel in mapper.relationships:
                parent = getattr(mapper.local_table, "name", str(mapper.local_table))
                child = getattr(
                    rel.entity.local_table, "name", str(rel.entity.local_table)
                )

                # Double }} for f-string escaping
                relation = "||--}}o" if rel.uselist else "||--||"
                relationship_lines.append(
                    f'  {parent} {relation} {child} : "{rel.key}"'
                )
    else:
        for table in metadata.tables.values():
            for fk in table.foreign_keys:
                parent = fk.column.table.name
                child = table.name
                # Double }} here as well
                relationship_lines.append(
                    f'  {parent} ||--}}o {child} : "{fk.parent.name}"'
                )

    # Sort relationships so the git diff stays clean
    lines.extend(sorted(relationship_lines))
    lines.append("```\n")
    return "\n".join(lines)


if __name__ == "__main__":
    print("Generating Mermaid ERD...\n")
    print(generate_mermaid())
    print("Mermaid ERD generation complete.")
