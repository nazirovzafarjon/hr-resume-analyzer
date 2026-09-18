from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserBase(BaseModel):
    email: EmailStr
    full_name: str


class UserCreate(UserBase):
    password: str


class UserUpdate(BaseModel):
    full_name: str | None = None
    password: str | None = None


class AdminUserUpdate(BaseModel):
    # Superuser can edit a user's profile/status flags.
    # All fields optional.


    full_name: str | None = None
    is_active: bool | None = None
    is_superuser: bool | None = None


class UserResponse(UserBase):
    id: int
    is_active: bool
    is_superuser: bool

    model_config = ConfigDict(from_attributes=True)


class UserProfileResponse(BaseModel):
    """The authenticated user's own profile, returned by the Settings endpoints.

    Deliberately smaller than the admin ``UserResponse``: it exposes only what
    the Settings page needs and never any password/security data. ``EmailStr``
    normalizes the address (lowercased) exactly like the auth endpoints.
    """

    id: int
    email: EmailStr
    full_name: str
    profile_image: str | None = None
    # Whether the account has a local password (false for Google-only
    # accounts, which cannot use the password-change flow). Mirrors the
    # existing ``ResetTokenInfo.has_password`` convention.
    has_password: bool

    model_config = ConfigDict(from_attributes=True)


class UserProfileUpdate(BaseModel):
    """Editable subset of the authenticated user's own profile.

    Both fields are optional so a client can update just one of them.
    """

    full_name: str | None = None
    email: EmailStr | None = None

    @field_validator("full_name")
    @classmethod
    def _trim_and_require_full_name(cls, value: str | None) -> str | None:
        """Trim surrounding whitespace and reject empty names.

        ``Field(min_length=1)`` alone would accept a name made of spaces, so
        the value is stripped first and then required to be non-empty.
        """
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Full name cannot be empty")
        return value


class ChangePasswordRequest(BaseModel):
    """Payload for changing the authenticated user's own password.

    ``new_password`` mirrors the existing password rules (see
    ``app.core.security``): required, and at most 72 characters because bcrypt
    only hashes its first 72 bytes.
    """

    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=1, max_length=72)