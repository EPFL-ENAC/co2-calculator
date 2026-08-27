"""Process emissions module package.

Importing this package registers the module and factor handlers
(metaclass side effect in ``handlers``/``factors``).
"""

from app.modules.process_emissions.data_entries import (
    ProcessEmissionsHandlerCreate,
    ProcessEmissionsHandlerResponse,
    ProcessEmissionsHandlerUpdate,
)
from app.modules.process_emissions.factors import (
    ProcessEmissionsFactorCreate,
    ProcessEmissionsFactorHandler,
    ProcessEmissionsFactorResponse,
    ProcessEmissionsFactorUpdate,
)
from app.modules.process_emissions.handlers import ProcessEmissionsModuleHandler

__all__ = [
    "ProcessEmissionsHandlerCreate",
    "ProcessEmissionsHandlerResponse",
    "ProcessEmissionsHandlerUpdate",
    "ProcessEmissionsFactorCreate",
    "ProcessEmissionsFactorHandler",
    "ProcessEmissionsFactorResponse",
    "ProcessEmissionsFactorUpdate",
    "ProcessEmissionsModuleHandler",
]
