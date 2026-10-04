"""Request/response bodies of the identity API (contracts/identity-contracts.md)."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
Visibility = Literal["public", "community", "leaderboard", "private"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LoginRequest(Strict):
    login: str = Field(min_length=1, max_length=256)
    password: str = Field(min_length=1, max_length=1024)


class RegisterRequest(Strict):
    login: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=1024)
    email: str | None = Field(default=None, max_length=320, pattern=EMAIL_PATTERN)


class VerifyRequest(Strict):
    token: str = Field(min_length=16, max_length=128)
    password: str | None = Field(default=None, max_length=1024)


class PasswordConfirmation(Strict):
    password: str = Field(min_length=1, max_length=1024)


class CredentialsConfirmation(Strict):
    login: str = Field(min_length=1, max_length=256)
    password: str = Field(min_length=1, max_length=1024)


class SessionInfo(BaseModel):
    user_id: UUID
    display_name: str | None
    csrf_token: str
    expires_at: datetime


class OnboardingStep(BaseModel):
    step: str
    completed_at: datetime | None


class Me(BaseModel):
    id: UUID
    login: str | None
    display_name: str | None
    email: str | None
    state: str
    created_at: datetime
    verified_at: datetime | None
    has_avatar: bool
    onboarding: list[OnboardingStep]
    deletion_due_at: datetime | None = None


class FieldUpdateBody(Strict):
    value: str | None = Field(default=None, max_length=1000)
    visibility: Visibility = "private"


class ProfilePatch(Strict):
    display_name: str | None = Field(default=None, max_length=64)
    fields: dict[str, FieldUpdateBody] | None = None


class ProfileFieldOut(BaseModel):
    key: str
    value: str | None
    visibility: Visibility


class ProfileOut(BaseModel):
    user_id: UUID
    display_name: str | None
    has_avatar: bool
    fields: list[ProfileFieldOut]


class AdminCreateUser(Strict):
    login: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=64)
    email: str | None = Field(default=None, max_length=320, pattern=EMAIL_PATTERN)


class VerificationTokenOut(BaseModel):
    user_id: UUID
    verification_token: str
    expires_at: datetime


class AdminReason(Strict):
    reason: str = Field(default="admin_action", min_length=1, max_length=64, pattern=r"^[a-z0-9_.:-]+$")


class UserListItem(BaseModel):
    id: UUID
    login: str | None
    display_name: str | None
    state: str
    created_at: datetime
    last_sign_in_at: datetime | None
    email: str | None = None  # administrators only (this list requires ``users.manage``)


class AdminEditUser(Strict):
    """027: what an administrator may correct on an account (empty e-mail removes it)."""

    display_name: str | None = Field(default=None, min_length=1, max_length=64)
    email: str | None = Field(default=None, max_length=320, pattern=r"^$|" + EMAIL_PATTERN)


class UserList(BaseModel):
    items: list[UserListItem]
    next_cursor: str | None


class AdminTransferRequest(Strict):
    target_user_id: UUID
    password: str = Field(min_length=1, max_length=1024)


class DeletionStatus(BaseModel):
    state: str
    deletion_due_at: datetime | None


class ExportOut(BaseModel):
    id: UUID
    status: str
    requested_at: datetime
    completed_at: datetime | None
    expires_at: datetime | None


class Accepted(BaseModel):
    status: Literal["accepted"] = "accepted"
    detail: str
