from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

from fastapi import Request
from sqlalchemy import String, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import TypeDecorator


class DecimalString(TypeDecorator):
    """Точное хранение денежных сумм и тарифов (SQLite не поддерживает Decimal)."""

    impl = String(40)
    cache_ok = True

    def __init__(self, places: int = 2):
        super().__init__()
        self.places = places

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return format(Decimal(value).quantize(Decimal(1).scaleb(-self.places)), "f")

    def process_result_value(self, value, dialect):
        return None if value is None else Decimal(value)


def make_engine(url: str) -> Engine:
    kwargs: dict = {}
    if url.startswith("sqlite"):
        path = url.removeprefix("sqlite:///")
        if path and path != ":memory:" and not url == "sqlite://":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        kwargs["connect_args"] = {"check_same_thread": False}
        if url in ("sqlite://", "sqlite:///:memory:"):
            kwargs["poolclass"] = StaticPool
    return create_engine(url, **kwargs)


def make_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, expire_on_commit=False)


def get_session(request: Request) -> Iterator[Session]:
    """FastAPI-зависимость: сессия БД своего сервиса (database per service)."""
    with request.app.state.session_factory() as session:
        yield session
