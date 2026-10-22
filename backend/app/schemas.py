import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl, field_validator, model_validator

CODE_RE = re.compile(r"^[A-Za-z0-9_-]{3,32}$")
RESERVED = {"api", "docs", "redoc", "openapi.json", "health", "admin", "login", "register", "static"}


class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)  # bcrypt only reads 72 bytes
    confirm_password: str

    @model_validator(mode="after")
    def passwords_match(self):
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: EmailStr


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class LinkCreate(BaseModel):
    original_url: HttpUrl
    custom_code: str | None = None
    title: str | None = Field(default=None, max_length=120)
    expires_at: datetime | None = None

    @field_validator("custom_code")
    @classmethod
    def valid_code(cls, v):
        if v is None or v == "":
            return None
        if not CODE_RE.match(v):
            raise ValueError("Code must be 3-32 characters: letters, numbers, - or _")
        if v.lower() in RESERVED:
            raise ValueError("That code is reserved")
        return v


class LinkUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=120)
    is_active: bool | None = None
    expires_at: datetime | None = None


class LinkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    short_url: str
    original_url: str
    title: str | None
    is_active: bool
    expires_at: datetime | None
    created_at: datetime
    total_clicks: int = 0


class DayCount(BaseModel):
    date: str
    clicks: int


class NameCount(BaseModel):
    name: str
    clicks: int


class StatsOut(BaseModel):
    code: str
    total_clicks: int
    clicks_per_day: list[DayCount]
    devices: list[NameCount]
    referrers: list[NameCount]
