from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from .enums import InsuranceType, PolicyStatus, TransactionStatus


class PolicyCreate(BaseModel):
    client_id: int = Field(gt=0)
    product_id: int = Field(gt=0)
    insured_amount: Decimal = Field(gt=Decimal("0"), max_digits=12, decimal_places=2)
    start_date: date | None = Field(default=None, description="По умолчанию — сегодня")
    claim_free_years: int = Field(default=0, ge=0, le=50)
    high_risk_zone: bool = False


class PolicyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    policy_id: int
    policy_number: str | None
    client_id: int
    product_id: int
    insurance_type: InsuranceType
    start_date: date
    end_date: date
    premium: Decimal
    insured_amount: Decimal
    is_paid: bool
    status: PolicyStatus


class PaymentCreate(BaseModel):
    amount: Decimal | None = Field(default=None, gt=Decimal("0"), max_digits=12, decimal_places=2,
                                   description="По умолчанию — неоплаченный остаток премии")


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    transaction_id: int
    policy_id: int
    amount: Decimal
    payment_date: datetime
    status: TransactionStatus
    created_at: datetime


class CoverageOut(BaseModel):
    """Ответ для Claim Service: действовал ли договор на дату события."""
    policy_id: int
    client_id: int
    insured_amount: Decimal
    covered: bool
    reason: str | None = None
