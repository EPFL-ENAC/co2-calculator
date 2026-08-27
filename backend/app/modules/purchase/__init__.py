"""Purchase module package.

Importing this package registers the module and factor handlers
(metaclass side effect in ``handlers``/``factors``).
"""

from app.modules.purchase.data_entries import (
    PurchaseCentralizedHandlerCreate,
    PurchaseCentralizedHandlerResponse,
    PurchaseCentralizedHandlerUpdate,
    PurchaseHandlerCreate,
    PurchaseHandlerResponse,
    PurchaseHandlerUpdate,
)
from app.modules.purchase.factors import (
    PurchaseCentralizedFactorCreate,
    PurchaseCentralizedFactorHandler,
    PurchaseCentralizedFactorResponse,
    PurchaseCentralizedFactorUpdate,
    PurchaseCommonFactorCreate,
    PurchaseCommonFactorHandler,
    PurchaseCommonFactorResponse,
    PurchaseCommonFactorUpdate,
)
from app.modules.purchase.handlers import (
    PurchaseCentralizedModuleHandler,
    PurchaseModuleHandler,
)

__all__ = [
    "PurchaseCentralizedHandlerCreate",
    "PurchaseCentralizedHandlerResponse",
    "PurchaseCentralizedHandlerUpdate",
    "PurchaseHandlerCreate",
    "PurchaseHandlerResponse",
    "PurchaseHandlerUpdate",
    "PurchaseCentralizedFactorCreate",
    "PurchaseCentralizedFactorHandler",
    "PurchaseCentralizedFactorResponse",
    "PurchaseCentralizedFactorUpdate",
    "PurchaseCommonFactorCreate",
    "PurchaseCommonFactorHandler",
    "PurchaseCommonFactorResponse",
    "PurchaseCommonFactorUpdate",
    "PurchaseCentralizedModuleHandler",
    "PurchaseModuleHandler",
]
