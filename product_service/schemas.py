from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from .models import InsuranceType, ProductStatus


class ProductIn(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    base_rate: Decimal = Field(gt=Decimal("0"), le=Decimal("1"), decimal_places=4,
                               description="Годовой тариф в долях от страховой суммы (0.05 = 5%)")
    insurance_type: InsuranceType
    status: ProductStatus = ProductStatus.ACTIVE


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: int
    name: str
    description: str | None
    base_rate: Decimal
    insurance_type: InsuranceType
    status: ProductStatus
