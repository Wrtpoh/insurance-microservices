import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


def normalize_phone(raw: str) -> str:
    """Телефон хранится в виде «+» и 10–15 цифр, остальные символы отбрасываются."""
    digits = re.sub(r"\D", "", raw)
    if not 10 <= len(digits) <= 15:
        raise ValueError("Телефон должен содержать от 10 до 15 цифр")
    return "+" + digits


class ClientIn(BaseModel):
    full_name: str = Field(min_length=3, max_length=255)
    phone: str
    email: str | None = Field(default=None, max_length=255)
    address: str | None = Field(default=None, max_length=500)

    @field_validator("full_name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if len(value) < 3:
            raise ValueError("ФИО слишком короткое")
        return value

    @field_validator("phone")
    @classmethod
    def check_phone(cls, value: str) -> str:
        return normalize_phone(value)

    @field_validator("email")
    @classmethod
    def check_email(cls, value: str | None) -> str | None:
        if value is not None and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("Некорректный адрес электронной почты")
        return value


class ClientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    client_id: int
    full_name: str
    phone: str
    email: str | None
    address: str | None
    created_at: datetime
