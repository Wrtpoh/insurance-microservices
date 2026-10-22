from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from .enums import ClaimStatus, PayoutRule, PayoutStatus


class ClaimCreate(BaseModel):
    policy_id: int = Field(gt=0)
    event_date: date
    description: str = Field(min_length=1, max_length=2000)
    documents: list[str] = Field(default_factory=list)
    damage_amount: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)


class ClaimUpdate(BaseModel):
    description: str | None = Field(default=None, min_length=1, max_length=2000)
    documents: list[str] | None = None
    damage_amount: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)


class ClaimOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    claim_id: int
    policy_id: int
    event_date: date
    description: str
    documents: list[str]
    damage_amount: Decimal | None
    status: ClaimStatus
    created_at: datetime


class PayoutCreate(BaseModel):
    claim_id: int = Field(gt=0)
    rule: PayoutRule = PayoutRule.FULL
    deductible: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    actual_value: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)


class PayoutOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    payout_id: int
    claim_id: int
    client_id: int
    amount: Decimal
    rule: str
    status: PayoutStatus
    created_at: datetime
    paid_at: datetime | None
