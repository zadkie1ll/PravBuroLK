from pydantic import BaseModel, ConfigDict, computed_field

from .config import can_manage_education


class LoginRequest(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    is_staff: bool
    role: str

    @computed_field
    @property
    def can_manage_education(self) -> bool:
        return can_manage_education(self.is_staff, self.role)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
