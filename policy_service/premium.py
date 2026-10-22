"""ПАТТЕРН: Decorator (структурный).

Страховая премия = базовый тариф продукта с набором необязательных скидок и надбавок.
Каждое правило оформлено декоратором, итоговый расчёт собирается цепочкой без класса на каждое сочетание.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


@dataclass(frozen=True)
class PremiumRequest:
    insured_amount: Decimal
    base_rate: Decimal
    term_months: int
    claim_free_years: int = 0
    high_risk_zone: bool = False


class PremiumCalculator(ABC):
    @abstractmethod
    def calculate(self, request: PremiumRequest) -> Decimal: ...


class BasePremiumCalculator(PremiumCalculator):
    """Премия = страховая сумма * годовой тариф * срок в годах."""

    def calculate(self, request: PremiumRequest) -> Decimal:
        value = request.insured_amount * request.base_rate * Decimal(request.term_months) / Decimal(12)
        return value.quantize(CENT, ROUND_HALF_UP)


class PremiumDecorator(PremiumCalculator):
    def __init__(self, wrapped: PremiumCalculator):
        self._wrapped = wrapped

    @staticmethod
    def _apply(value: Decimal, coefficient: str) -> Decimal:
        return (value * Decimal(coefficient)).quantize(CENT, ROUND_HALF_UP)


class ClaimFreeDiscount(PremiumDecorator):
    """Скидка 10%, если у клиента не было страховых случаев 3 года и более."""

    def calculate(self, request: PremiumRequest) -> Decimal:
        value = self._wrapped.calculate(request)
        return self._apply(value, "0.90") if request.claim_free_years >= 3 else value


class RiskZoneSurcharge(PremiumDecorator):
    """Надбавка 20% для объектов в зоне повышенного риска."""

    def calculate(self, request: PremiumRequest) -> Decimal:
        value = self._wrapped.calculate(request)
        return self._apply(value, "1.20") if request.high_risk_zone else value


class LongTermDiscount(PremiumDecorator):
    """Скидка 5% на договоры сроком от 36 месяцев."""

    def calculate(self, request: PremiumRequest) -> Decimal:
        value = self._wrapped.calculate(request)
        return self._apply(value, "0.95") if request.term_months >= 36 else value


def default_calculator() -> PremiumCalculator:
    return LongTermDiscount(RiskZoneSurcharge(ClaimFreeDiscount(BasePremiumCalculator())))
