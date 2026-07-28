from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LoginRequest(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    is_staff: bool
    sales_manager_id: int | None = None
    sales_manager_name: str = ""


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class SalesManagerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    phone: str = ""
    bitrix_user_id: int
    is_active: bool
    megafon_user: str = ""
    megafon_group: str = ""
    megafon_clid: str = ""


class ManagerStats(BaseModel):
    manager: SalesManagerOut
    period_start: datetime
    period_end: datetime
    total_time: str
    call_count: int


class SalesManagerAdminRow(BaseModel):
    id: int
    name: str
    bitrix_user_id: int
    megafon_user: str = ""
    megafon_clid: str = ""
    email: str = ""
    phone: str = ""
    user_username: str | None = None
    is_active: bool
    updated_at: datetime


class SalesManagerListResponse(BaseModel):
    results: list[SalesManagerAdminRow]
    count: int
    page: int
    per_page: int


class LeadSourceAdminRow(BaseModel):
    id: int
    name: str
    bitrix_id: int | None = None
    is_active: bool
    created_at: datetime


class LeadSourceListResponse(BaseModel):
    results: list[LeadSourceAdminRow]
    count: int
    page: int
    per_page: int


class IsActivePatch(BaseModel):
    is_active: bool


class SyncResult(BaseModel):
    ok: bool
    total_from_bitrix: int
    created: int
    updated: int
    deactivated: int
    synced_at: str
    django_users_created: int | None = None
    new_credentials: list[dict] | None = None
