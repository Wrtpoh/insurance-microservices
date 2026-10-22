"""ПАТТЕРН: Builder (порождающий).

Заявление о страховом случае: обязательные поля (договор, дата, описание) и необязательные
(документы, заявленный ущерб). Строитель собирает объект пошагово и проверяет его в build().
"""
from datetime import date
from decimal import Decimal

from common.errors import Unprocessable

from .models import Claim


class ClaimBuilder:
    def __init__(self, policy_id: int):
        self._policy_id = policy_id
        self._event_date: date | None = None
        self._description: str | None = None
        self._documents: list[str] = []
        self._damage_amount: Decimal | None = None

    @classmethod
    def for_policy(cls, policy_id: int) -> "ClaimBuilder":
        return cls(policy_id)

    def event_date(self, value: date) -> "ClaimBuilder":
        self._event_date = value
        return self

    def description(self, value: str) -> "ClaimBuilder":
        self._description = value
        return self

    def add_document(self, name: str) -> "ClaimBuilder":
        self._documents.append(name)
        return self

    def damage_amount(self, value: Decimal | None) -> "ClaimBuilder":
        self._damage_amount = value
        return self

    def build(self) -> Claim:
        if self._policy_id <= 0:
            raise Unprocessable("Не указан договор")
        if self._event_date is None:
            raise Unprocessable("Не указана дата события")
        if self._event_date > date.today():
            raise Unprocessable("Дата события не может быть в будущем")
        if not self._description or not self._description.strip():
            raise Unprocessable("Не заполнено описание события")
        if self._damage_amount is not None and self._damage_amount < 0:
            raise Unprocessable("Сумма ущерба не может быть отрицательной")
        return Claim(policy_id=self._policy_id, event_date=self._event_date,
                     description=self._description.strip(), documents=list(self._documents),
                     damage_amount=self._damage_amount)
