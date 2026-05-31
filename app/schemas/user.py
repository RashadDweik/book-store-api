from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, computed_field, field_validator

from .role import RoleRead


class UserBase(BaseModel):
    # Shared fields for user inputs and responses.
    email: EmailStr
    full_name: str = Field(min_length=2)


class UserCreate(UserBase):
    # Payload for creating a user with password validation rules.
    password: str = Field(min_length=8)
    role_id: UUID | None = Field(
        default=None,
        description="Defaults to the 'user' role when omitted.",
    )

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not any(char.isupper() for char in value):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not any(char.isdigit() for char in value):
            raise ValueError("Password must contain at least one digit.")
        return value


class UserUpdate(BaseModel):
    # Partial update payload for editable profile fields.
    full_name: str | None = Field(default=None, min_length=2)
    email: EmailStr | None = None


class UserResponse(UserBase):
    # API response shape for user data.
    id: UUID
    is_active: bool
    created_at: datetime
    role: RoleRead | None = Field(default=None, exclude=True)

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def is_admin(self) -> bool:
        return bool(self.role and self.role.name == "admin")


class TokenResponse(BaseModel):
    # Access token response payload.
    access_token: str
    token_type: str = "bearer"

    model_config = ConfigDict(from_attributes=True)


class RefreshRequest(BaseModel):
    # Legacy request model kept for older non-browser clients.
    refresh_token: str | None = None


class LogoutRequest(BaseModel):
    # Legacy request model kept for older non-browser clients.
    refresh_token: str | None = None
