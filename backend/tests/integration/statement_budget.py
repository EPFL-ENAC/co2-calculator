"""SQL-statement counting for budget tests.

Lifted verbatim out of the two ingestion budget tests once a third caller
appeared (#2527 task 6). A ``before_cursor_execute`` listener is the only
place that sees what the driver actually sends — psycopg3 batches some
round trips, so counting at the ORM layer would lie.
"""

import re
from contextlib import contextmanager
from dataclasses import dataclass, field

from sqlalchemy import event

SELECT_RE = re.compile(r"^SELECT", re.IGNORECASE)


@dataclass
class StatementLog:
    statements: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.statements)

    @property
    def selects(self) -> int:
        return sum(1 for s in self.statements if SELECT_RE.match(s.strip()))

    def by_table(self) -> dict[str, int]:
        """Rough per-table tally — enough to see an N+1 without reading 40 lines."""
        counts: dict[str, int] = {}
        for statement in self.statements:
            match = re.search(
                r"\bFROM\s+([a-z_]+)|\bINTO\s+([a-z_]+)|\bUPDATE\s+([a-z_]+)",
                statement,
                re.IGNORECASE,
            )
            table = next((g for g in (match.groups() if match else ()) if g), "?")
            counts[table] = counts.get(table, 0) + 1
        return dict(sorted(counts.items(), key=lambda kv: -kv[1]))

    def breakdown(self) -> str:
        return f"total={self.total} selects={self.selects} {self.by_table()}"

    def numbered(self) -> str:
        return "\n".join(
            f"  {i:>2}. {' '.join(s.split())[:110]}"
            for i, s in enumerate(self.statements, 1)
        )


@contextmanager
def count_statements(engine):
    log = StatementLog()

    def listener(conn, cursor, statement, parameters, context, executemany):
        log.statements.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", listener)
    try:
        yield log
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", listener)
