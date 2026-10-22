"""ПАТТЕРН: Factory Method (порождающий).

Договоры разных типов страхования отличаются сроком и минимальной страховой суммой.
Общий алгоритм (проверка суммы, присвоение номера) находится в базовом классе, а конкретный
договор создаёт фабричный метод create_policy, который переопределяют подклассы.
"""
from abc import ABC, abstractmethod
from datetime import date
from decimal import Decimal

from common.errors import Unprocessable

from .dates import policy_end
from .enums import InsuranceType
from .models import Policy


class PolicyFactory(ABC):
    insurance_type: InsuranceType
    code: str
    term_months: int
    min_insured_amount: Decimal

    def issue(self, client_id: int, product_id: int, insured_amount: Decimal, start_date: date) -> Policy:
        if insured_amount < self.min_insured_amount:
            raise Unprocessable(f"Страховая сумма по виду {self.insurance_type.value} "
                                f"не может быть меньше {self.min_insured_amount}")
        return self.create_policy(client_id, product_id, insured_amount, start_date)

    @abstractmethod
    def create_policy(self, client_id: int, product_id: int, insured_amount: Decimal,
                      start_date: date) -> Policy:
        """Фабричный метод: создаёт договор конкретного типа."""

    def assign_number(self, policy: Policy) -> None:
        policy.policy_number = f"POL-{self.code}-{policy.policy_id:06d}"

    def _build(self, client_id, product_id, insured_amount, start_date) -> Policy:
        return Policy(client_id=client_id, product_id=product_id,
                      insurance_type=self.insurance_type.value, insured_amount=insured_amount,
                      start_date=start_date, end_date=policy_end(start_date, self.term_months))


class AutoPolicyFactory(PolicyFactory):
    insurance_type, code, term_months = InsuranceType.AUTO, "AUTO", 12
    min_insured_amount = Decimal("300000")  # КАСКО

    def create_policy(self, client_id, product_id, insured_amount, start_date) -> Policy:
        return self._build(client_id, product_id, insured_amount, start_date)


class HealthPolicyFactory(PolicyFactory):
    insurance_type, code, term_months = InsuranceType.HEALTH, "HLT", 12
    min_insured_amount = Decimal("50000")

    def create_policy(self, client_id, product_id, insured_amount, start_date) -> Policy:
        return self._build(client_id, product_id, insured_amount, start_date)


class PropertyPolicyFactory(PolicyFactory):
    insurance_type, code, term_months = InsuranceType.PROPERTY, "PRP", 36  # многолетний полис имущества??
    min_insured_amount = Decimal("300000")

    def create_policy(self, client_id, product_id, insured_amount, start_date) -> Policy:
        return self._build(client_id, product_id, insured_amount, start_date)


_FACTORIES: dict[InsuranceType, type[PolicyFactory]] = {
    InsuranceType.AUTO: AutoPolicyFactory,
    InsuranceType.HEALTH: HealthPolicyFactory,
    InsuranceType.PROPERTY: PropertyPolicyFactory,
}


def factory_for(insurance_type: InsuranceType | str) -> PolicyFactory:
    return _FACTORIES[InsuranceType(insurance_type)]()
