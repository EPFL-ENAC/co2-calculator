"""External cloud and AI module package.

Importing this package registers the module and factor handlers
(metaclass side effect in ``handlers``/``factors``).
"""

from app.modules.external_cloud_and_ai.data_entries import (
    REQUESTS_FREQUENCY_MAP,
    REQUESTS_FREQUENCY_OPTIONS,
    ExternalAIHandlerCreate,
    ExternalAIHandlerResponse,
    ExternalAIHandlerUpdate,
    ExternalCloudHandlerCreate,
    ExternalCloudHandlerResponse,
    ExternalCloudHandlerUpdate,
)
from app.modules.external_cloud_and_ai.factors import (
    ExternalAIFactorCreate,
    ExternalAIFactorHandler,
    ExternalAIFactorResponse,
    ExternalAIFactorUpdate,
    ExternalCloudFactorCreate,
    ExternalCloudFactorHandler,
    ExternalCloudFactorResponse,
    ExternalCloudFactorUpdate,
)
from app.modules.external_cloud_and_ai.handlers import (
    ExternalAIModuleHandler,
    ExternalCloudModuleHandler,
)

__all__ = [
    "REQUESTS_FREQUENCY_MAP",
    "REQUESTS_FREQUENCY_OPTIONS",
    "ExternalAIHandlerCreate",
    "ExternalAIHandlerResponse",
    "ExternalAIHandlerUpdate",
    "ExternalCloudHandlerCreate",
    "ExternalCloudHandlerResponse",
    "ExternalCloudHandlerUpdate",
    "ExternalAIFactorCreate",
    "ExternalAIFactorHandler",
    "ExternalAIFactorResponse",
    "ExternalAIFactorUpdate",
    "ExternalCloudFactorCreate",
    "ExternalCloudFactorHandler",
    "ExternalCloudFactorResponse",
    "ExternalCloudFactorUpdate",
    "ExternalAIModuleHandler",
    "ExternalCloudModuleHandler",
]
