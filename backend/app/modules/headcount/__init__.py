"""Headcount module package.

Importing this package registers the module and factor handlers
(metaclass side effect in ``handlers``/``factors``).
"""

from app.modules.headcount.data_entries import (
    OTHER_SIUS_CODE,
    SIUS_CODE_VALUES,
    HeadCountCreate,
    HeadcountItemResponse,
    HeadcountMemberDropdownItem,
    HeadCountStudentCreate,
    HeadCountStudentResponse,
    HeadCountStudentUpdate,
    HeadCountUpdate,
    normalize_sius_code,
)
from app.modules.headcount.factors import (
    HeadcountFactorCreate,
    HeadcountFactorResponse,
    HeadcountFactorUpdate,
    HeadcountMemberFactorHandler,
    HeadcountStudentFactorHandler,
)
from app.modules.headcount.handlers import (
    HeadcountMemberModuleHandler,
    HeadcountStudentModuleHandler,
)

__all__ = [
    "OTHER_SIUS_CODE",
    "SIUS_CODE_VALUES",
    "normalize_sius_code",
    "HeadCountCreate",
    "HeadCountStudentCreate",
    "HeadCountStudentResponse",
    "HeadCountStudentUpdate",
    "HeadCountUpdate",
    "HeadcountItemResponse",
    "HeadcountMemberDropdownItem",
    "HeadcountFactorCreate",
    "HeadcountFactorResponse",
    "HeadcountFactorUpdate",
    "HeadcountMemberFactorHandler",
    "HeadcountStudentFactorHandler",
    "HeadcountMemberModuleHandler",
    "HeadcountStudentModuleHandler",
]
