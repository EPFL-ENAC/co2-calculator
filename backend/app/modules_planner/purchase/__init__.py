"""Planner purchases: manual EUR totals per submodule XOR one global budget.

Importing this package registers the module and factor handlers
(metaclass side effect in ``handlers``/``factors``).
"""

from app.modules_planner.purchase.data_entries import (
    PURCHASE_SUBMODULE_CATEGORIES,
    PlannerPurchaseBudgetCreate,
    PlannerPurchaseBudgetResponse,
    PlannerPurchaseBudgetUpdate,
    PlannerPurchaseCreate,
    PlannerPurchaseResponse,
    PlannerPurchaseUpdate,
)
from app.modules_planner.purchase.factors import (
    PlannerPurchaseBudgetFactorHandler,
    PlannerPurchaseFactorHandler,
)
from app.modules_planner.purchase.handlers import (
    PlannerPurchaseBudgetModuleHandler,
    PlannerPurchaseModuleHandler,
)

__all__ = [
    "PURCHASE_SUBMODULE_CATEGORIES",
    "PlannerPurchaseBudgetCreate",
    "PlannerPurchaseBudgetResponse",
    "PlannerPurchaseBudgetUpdate",
    "PlannerPurchaseCreate",
    "PlannerPurchaseResponse",
    "PlannerPurchaseUpdate",
    "PlannerPurchaseBudgetFactorHandler",
    "PlannerPurchaseFactorHandler",
    "PlannerPurchaseBudgetModuleHandler",
    "PlannerPurchaseModuleHandler",
]
