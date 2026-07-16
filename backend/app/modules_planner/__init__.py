"""Simulator Plan (planner) module handlers.

Planner modules whose entry shape differs from the Calculator live here,
one subpackage per module (mirroring ``app/modules``). Importing this
package registers their handlers in the shared ``MODULE_HANDLERS``
registry; their ``FactorQuery`` points at existing Calculator factors —
no planner-specific factor rows exist.
"""

import app.modules_planner.headcount  # noqa: F401  # registers the handlers
import app.modules_planner.purchase  # noqa: F401  # registers the handlers
