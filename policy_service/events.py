"""ПАТТЕРН: Observer (поведенческий).

После подтверждения платежа нужно выставить is_paid, активировать договор и записать событие в журнал.
PaymentService не знает об этих действиях: подписчики подключаются к издателю событий.
"""
import logging
from dataclasses import dataclass
from typing import Protocol

from .enums import PolicyStatus
from .models import Policy, Transaction

logger = logging.getLogger("insurance.audit")


@dataclass(frozen=True)
class PaymentConfirmed:
    transaction: Transaction
    policy: Policy


class PaymentListener(Protocol):
    def on_payment_confirmed(self, event: PaymentConfirmed) -> None: ...


class EventPublisher:
    def __init__(self):
        self._listeners: list[PaymentListener] = []

    def subscribe(self, listener: PaymentListener) -> None:
        self._listeners.append(listener)

    def unsubscribe(self, listener: PaymentListener) -> None:
        self._listeners.remove(listener)

    def publish(self, event: PaymentConfirmed) -> None:
        for listener in list(self._listeners):
            listener.on_payment_confirmed(event)


class PolicyActivationListener:
    """Когда оплачена вся премия, договор отмечается оплаченным и активируется."""

    def on_payment_confirmed(self, event: PaymentConfirmed) -> None:
        policy = event.policy
        if policy.paid_total() >= policy.premium:
            policy.is_paid = True
            if policy.status == PolicyStatus.CREATED.value:
                policy.status = PolicyStatus.ACTIVE.value


class AuditLogListener:
    """Журналирование подтверждённых платежей."""

    def __init__(self):
        self.entries: list[str] = []

    def on_payment_confirmed(self, event: PaymentConfirmed) -> None:
        entry = (f"Платёж {event.transaction.transaction_id} по договору {event.policy.policy_number} "
                 f"на сумму {event.transaction.amount} подтверждён")
        self.entries.append(entry)
        logger.info(entry)
