from pydantic import BaseModel, EmailStr, Field, validator
from datetime import datetime

class UserData(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(min_length=6, max_length=64)
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @validator("name")
    def strip_name(cls, value: str) -> str:
        return value.strip()

    @validator("password")
    def validate_password(cls, value: str) -> str:
        if " " in value:
            raise ValueError("Password cannot contain spaces")
        # ✅ return plain password; hashing happens in routes
        return value
