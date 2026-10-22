from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from common.db import DecimalString

from .enums import PolicyStatus, TransactionStatus


class Base(DeclarativeBase):
    pass


class Policy(Base):
    __tablename__ = "policies"

    policy_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    policy_number: Mapped[str | None] = mapped_column(String(30), unique=True, nullable=True)
    client_id: Mapped[int] = mapped_column(Integer, index=True)
    product_id: Mapped[int] = mapped_column(Integer)
    insurance_type: Mapped[str] = mapped_column(String(20))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    premium: Mapped[Decimal] = mapped_column(DecimalString(2), default=Decimal("0"))
    insured_amount: Mapped[Decimal] = mapped_column(DecimalString(2))
    is_paid: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default=PolicyStatus.CREATED.value)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="policy",
                                                             order_by="Transaction.transaction_id")

    def paid_total(self) -> Decimal:
        return sum((t.amount for t in self.transactions
                    if t.status == TransactionStatus.COMPLETED.value), Decimal("0"))


class Transaction(Base):
    __tablename__ = "transactions"

    transaction_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    policy_id: Mapped[int] = mapped_column(ForeignKey("policies.policy_id"), index=True)
    amount: Mapped[Decimal] = mapped_column(DecimalString(2))
    payment_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    status: Mapped[str] = mapped_column(String(20), default=TransactionStatus.PENDING.value)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    policy: Mapped[Policy] = relationship(back_populates="transactions")
