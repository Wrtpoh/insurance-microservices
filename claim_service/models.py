from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from common.db import DecimalString

from .enums import ClaimStatus, PayoutStatus


class Base(DeclarativeBase):
    pass


class Claim(Base):
    __tablename__ = "claims"

    claim_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    policy_id: Mapped[int] = mapped_column(Integer, index=True)
    event_date: Mapped[date] = mapped_column(Date)
    description: Mapped[str] = mapped_column(String(2000))
    documents: Mapped[list] = mapped_column(JSON, default=list)
    damage_amount: Mapped[Decimal | None] = mapped_column(DecimalString(2), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=ClaimStatus.CREATED.value)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    # Переходы между статусами делегируются состоянию (паттерн State, см. state.py)
    def _state(self):
        from .state import state_for
        return state_for(self.status)

    def start_review(self) -> None:
        self._state().start_review(self)

    def approve(self) -> None:
        self._state().approve(self)

    def reject(self) -> None:
        self._state().reject(self)

    def close(self) -> None:
        self._state().close(self)


class Payout(Base):
    __tablename__ = "payouts"

    payout_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.claim_id"), unique=True)  # связь 1:1
    client_id: Mapped[int] = mapped_column(Integer)
    amount: Mapped[Decimal] = mapped_column(DecimalString(2))
    rule: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default=PayoutStatus.CREATED.value)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
