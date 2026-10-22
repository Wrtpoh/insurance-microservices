import re

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from common.errors import Conflict, NotFound

from .models import Client
from .schemas import ClientIn


class ClientService:
    """Правила работы с клиентами: уникальность телефона, поиск по ФИО и телефону."""

    def __init__(self, session: Session):
        self.session = session

    def _phone_taken(self, phone: str, except_id: int | None = None) -> bool:
        stmt = select(Client.client_id).where(Client.phone == phone)
        if except_id is not None:
            stmt = stmt.where(Client.client_id != except_id)
        return self.session.scalar(stmt) is not None

    def create(self, data: ClientIn) -> Client:
        if self._phone_taken(data.phone):
            raise Conflict(f"Клиент с телефоном {data.phone} уже зарегистрирован")
        client = Client(**data.model_dump(), name_key=data.full_name.casefold())
        self.session.add(client)
        self.session.commit()
        return client

    def get(self, client_id: int) -> Client:
        client = self.session.get(Client, client_id)
        if client is None:
            raise NotFound(f"Клиент {client_id} не найден")
        return client

    def update(self, client_id: int, data: ClientIn) -> Client:
        client = self.get(client_id)
        if self._phone_taken(data.phone, except_id=client_id):
            raise Conflict(f"Телефон {data.phone} принадлежит другому клиенту")
        for field, value in data.model_dump().items():
            setattr(client, field, value)
        client.name_key = data.full_name.casefold()
        self.session.commit()
        return client

    def search(self, query: str | None, limit: int = 50, offset: int = 0) -> list[Client]:
        stmt = select(Client).order_by(Client.client_id).limit(limit).offset(offset)
        if query:
            digits = re.sub(r"\D", "", query)
            conditions = [Client.name_key.like(f"%{query.strip().casefold()}%")]
            if digits:
                conditions.append(Client.phone.like(f"%{digits}%"))
            stmt = stmt.where(or_(*conditions))
        return list(self.session.scalars(stmt))
