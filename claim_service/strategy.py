"""ПАТТЕРН: Strategy (поведенческий).

Сумма выплаты считается по-разному: полное покрытие, франшиза, неполное страхование.
Каждое правило — отдельная стратегия, выбираемая при создании выплаты.
"""
from abc import ABC, abstractmethod
from decimal import ROUND_HALF_UP, Decimal

from common.errors import Unprocessable

from .enums import PayoutRule

CENT = Decimal("0.01")


class PayoutStrategy(ABC):
    @abstractmethod
    def calculate(self, damage: Decimal, insured_amount: Decimal) -> Decimal: ...

    @abstractmethod
    def describe(self) -> str: ...


class FullCoverage(PayoutStrategy):
    def calculate(self, damage, insured_amount):
        return min(damage, insured_amount).quantize(CENT, ROUND_HALF_UP)

    def describe(self):
        return "FULL: полное покрытие"


class Deductible(PayoutStrategy):
    def __init__(self, deductible: Decimal):
        self.deductible = deductible

    def calculate(self, damage, insured_amount):
        return min(max(damage - self.deductible, Decimal(0)), insured_amount).quantize(CENT, ROUND_HALF_UP)

    def describe(self):
        return f"DEDUCTIBLE: франшиза {self.deductible}"


class Proportional(PayoutStrategy):
    """Неполное страхование: ущерб возмещается в доле «страховая сумма / действительная стоимость»."""

    def __init__(self, actual_value: Decimal):
        self.actual_value = actual_value

    def calculate(self, damage, insured_amount):
        if insured_amount >= self.actual_value:
            return min(damage, insured_amount).quantize(CENT, ROUND_HALF_UP)
        return min(damage * insured_amount / self.actual_value, insured_amount).quantize(CENT, ROUND_HALF_UP)

    def describe(self):
        return f"PROPORTIONAL: стоимость объекта {self.actual_value}"


def strategy_for(rule: PayoutRule, deductible: Decimal | None, actual_value: Decimal | None) -> PayoutStrategy:
    if rule == PayoutRule.FULL:
        return FullCoverage()
    if rule == PayoutRule.DEDUCTIBLE:
        if deductible is None:
            raise Unprocessable("Для правила DEDUCTIBLE нужно указать франшизу (deductible)")
        return Deductible(deductible)
    if actual_value is None or actual_value <= 0:
        raise Unprocessable("Для правила PROPORTIONAL нужно указать действительную стоимость (actual_value)")
    return Proportional(actual_value)
