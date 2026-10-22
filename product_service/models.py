from decimal import Decimal
from enum import StrEnum

from sqlalchemy import Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from common.db import DecimalString


class Base(DeclarativeBase):
    pass


class InsuranceType(StrEnum):
    AUTO = "AUTO"
    HEALTH = "HEALTH"
    PROPERTY = "PROPERTY"


class ProductStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class Product(Base):
    __tablename__ = "products"

    product_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    base_rate: Mapped[Decimal] = mapped_column(DecimalString(4))
    insurance_type: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default=ProductStatus.ACTIVE.value)
