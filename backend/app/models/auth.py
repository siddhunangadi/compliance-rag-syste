from pydantic import BaseModel, EmailStr


class CurrentUser(BaseModel):
    """Authenticated user extracted from a verified Supabase token."""

    id: str
    email: EmailStr | None = None