from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Client(Base):
    __tablename__ = "clients"

    client_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(255))
    name_key: Mapped[str] = mapped_column(String(255), index=True)  # ФИО в нижнем регистре для поиска
    phone: Mapped[str] = mapped_column(String(20), unique=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
