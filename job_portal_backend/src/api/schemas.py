from pydantic import BaseModel, EmailStr, Field
from enum import Enum

class UserRole(str, Enum):
    employer = "employer"
    seeker = "seeker"

class UserBase(BaseModel):
    email: EmailStr = Field(..., description="User email")

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)
    role: UserRole

class UserOut(UserBase):
    id: int
    role: UserRole
    is_active: bool

    class Config:
        orm_mode = True

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    user_id: int
    email: EmailStr
    role: UserRole
