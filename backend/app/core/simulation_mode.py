"""Simulation-mode request flag (context-local).

Used to bypass module permission checks ONLY for simulation pages.
"""

from __future__ import annotations

from contextvars import ContextVar

SIMULATION_MODE: ContextVar[bool] = ContextVar("SIMULATION_MODE", default=False)
