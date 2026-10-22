"""ПАТТЕРН: Adapter (структурный).

Внешний банковский клиент принимает сумму в копейках и возвращает числовой код, а Policy Service
работает с рублями и статусами транзакций. Адаптер приводит банк к интерфейсу PaymentGateway.
"""
from abc import ABC, abstractmethod
from decimal import Decimal

from .enums import TransactionStatus


class PaymentGateway(ABC):
    @abstractmethod
    def charge(self, policy_number: str, amount: Decimal) -> TransactionStatus: ...


class LegacyBankClient:
    """Имитация готового внешнего клиента банка (его интерфейс менять нельзя)."""

    OK = 0
    INVALID_ACCOUNT = 14
    INSUFFICIENT_FUNDS = 51
    LIMIT_KOPECKS = 100_000_000  # свыше 1 000 000 руб. банк отклоняет платёж

    def send_payment(self, account: str, kopecks: int, currency_code: str) -> int:
        if not account:
            return self.INVALID_ACCOUNT
        if kopecks > self.LIMIT_KOPECKS:
            return self.INSUFFICIENT_FUNDS
        return self.OK


class BankPaymentAdapter(PaymentGateway):
    def __init__(self, bank: LegacyBankClient | None = None):
        self._bank = bank or LegacyBankClient()

    def charge(self, policy_number: str, amount: Decimal) -> TransactionStatus:
        kopecks = int(amount * 100)
        code = self._bank.send_payment(policy_number, kopecks, "RUB")
        return TransactionStatus.COMPLETED if code == LegacyBankClient.OK else TransactionStatus.FAILED
