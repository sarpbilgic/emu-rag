from pydantic import BaseModel, EmailStr

class UserRead(BaseModel):
    id: int
    username: str
    email: EmailStr

    class Config:
        from_attributes = True
