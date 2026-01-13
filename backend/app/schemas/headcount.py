from datetime import date as dt_date
from typing import List, Optional

from pydantic import BaseModel, Field

# ==========================================
# 3. API INPUT MODELS (DTOs)
# ==========================================


class HeadCountCreate(BaseModel):
    """
    Body payload for POST requests.
    Exact copy of Base (all fields required), but no ID/Audit/Provider allowed.
    """

    pass


class HeadCountCreateRequest(BaseModel):
    """
    Body payload for POST requests.
    Exact copy of Base (all fields required), but no ID/Audit/Provider allowed.
    """

    display_name: str | None = None
    function: str | None = None
    fte: float | None = None


class HeadCountUpdate(BaseModel):
    """
    Body payload for PATCH requests.
    All fields are Optional. We do NOT inherit from Base to avoid
    required field conflicts.
    """

    date: Optional[dt_date] = None
    unit_id: Optional[int] = None
    unit_name: Optional[str] = None
    cf: Optional[str] = None
    cf_name: Optional[str] = None
    cf_user_id: Optional[str] = None
    display_name: Optional[str] = None
    status: Optional[str] = None
    function: Optional[str] = None
    sciper: Optional[str] = None
    fte: Optional[float] = None
    # We might allow updating the provider manually, or handle it in code
    provider: Optional[str] = None
    function_role: Optional[str] = None


class HeadCountUpdateRequest(BaseModel):
    """
    Body payload for PATCH requests.
    All fields are Optional. We do NOT inherit from Base to avoid
    required field conflicts.
    """

    display_name: Optional[str] = None
    function: Optional[str] = None
    fte: Optional[float] = None


# ==========================================
# 4. API OUTPUT MODELS (DTOs)
# ==========================================


class HeadCountRead(BaseModel):
    """
    Response schema for GET requests.
    Returns Data + ID + Provider.
    """

    id: int
    provider: Optional[str]


class HeadcountItemResponse(BaseModel):
    """
    Response schema for Headcount items in Equipment submodule.
    """

    id: int = Field(..., description="Headcount record identifier")
    display_name: Optional[str] = Field(None, description="Display name of the person")
    function: Optional[str] = Field(None, description="Function or role")
    sciper: Optional[str] = Field(None, description="Sciper number")
    fte: float = Field(..., description="Full-time equivalent percentage (0.0 to 1.0)")


class HeadCountList(BaseModel):
    """
    Response schema for Paginated Lists.
    """

    items: List[HeadCountRead]
    total: int
    page: int
    page_size: int

    @property
    def total_pages(self) -> int:
        if self.page_size == 0:
            return 0
        return (self.total + self.page_size - 1) // self.page_size
