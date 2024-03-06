from typing import Optional

from pydantic import EmailStr

from beanie import Document


class User(Document):
    class Settings:
        name = "user"

    name: Optional[str] = None
    email: EmailStr
    identity: str
