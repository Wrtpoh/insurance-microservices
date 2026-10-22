from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from common.errors import Conflict, NotFound, Unprocessable

from .dates import add_months
from .enums import PolicyStatus, TransactionStatus
from .events import EventPublisher, PaymentConfirmed
from .factory import factory_for
from .models import Policy, Transaction
from .payment_gateway import PaymentGateway
from .schemas import CoverageOut


class PolicyService:
    """Жизненный цикл договора и учёт оплаты страховой премии."""

    def __init__(self, session: Session, gateway: PaymentGateway, publisher: EventPublisher):
        self.session = session
        self.gateway = gateway
        self.publisher = publisher

    # ---- договоры
    def get(self, policy_id: int) -> Policy:
        policy = self.session.get(Policy, policy_id)
        if policy is None:
            raise NotFound(f"Договор {policy_id} не найден")
        if policy.status == PolicyStatus.ACTIVE.value and policy.end_date < date.today():
            policy.status = PolicyStatus.EXPIRED.value
            self.session.commit()
        return policy

    def list(self, client_id: int | None) -> list[Policy]:
        stmt = select(Policy).order_by(Policy.policy_id)
        if client_id is not None:
            stmt = stmt.where(Policy.client_id == client_id)
        return list(self.session.scalars(stmt))

    def activate(self, policy_id: int) -> Policy:
        policy = self.get(policy_id)
        if policy.status != PolicyStatus.CREATED.value:
            raise Conflict(f"Активировать можно только договор в статусе CREATED, а не {policy.status}")
        if not policy.is_paid:
            raise Conflict("Договор нельзя активировать: премия не оплачена")
        policy.status = PolicyStatus.ACTIVE.value
        self.session.commit()
        return policy

    def renew(self, policy_id: int) -> Policy:
        policy = self.get(policy_id)
        if policy.status not in (PolicyStatus.ACTIVE.value, PolicyStatus.EXPIRED.value):
            raise Conflict(f"Продлить можно только действующий или истёкший договор, а не {policy.status}")
        term = factory_for(policy.insurance_type).term_months
        policy.end_date = add_months(policy.end_date, term)
        policy.status = PolicyStatus.ACTIVE.value
        self.session.commit()
        return policy

    def cancel(self, policy_id: int) -> Policy:
        policy = self.get(policy_id)
        if policy.status == PolicyStatus.CANCELLED.value:
            raise Conflict("Договор уже отменён")
        policy.status = PolicyStatus.CANCELLED.value
        self.session.commit()
        return policy

    def coverage(self, policy_id: int, on_date: date) -> CoverageOut:
        """Проверка для Claim Service: договор оплачен и действовал на дату события."""
        policy = self.get(policy_id)
        reason = None
        if policy.status == PolicyStatus.CANCELLED.value:
            reason = "Договор отменён"
        elif not policy.is_paid or policy.status == PolicyStatus.CREATED.value:
            reason = "Страховая премия по договору не оплачена"
        elif not policy.start_date <= on_date <= policy.end_date:
            reason = (f"Дата события {on_date} вне периода действия договора "
                      f"({policy.start_date} – {policy.end_date})")
        return CoverageOut(policy_id=policy.policy_id, client_id=policy.client_id,
                           insured_amount=policy.insured_amount, covered=reason is None, reason=reason)

    # ---- платежи
    def register_payment(self, policy_id: int, amount: Decimal | None) -> Transaction:
        policy = self.get(policy_id)
        if policy.status == PolicyStatus.CANCELLED.value:
            raise Conflict("Договор отменён, платёж зарегистрировать нельзя")
        pending = sum((t.amount for t in policy.transactions
                       if t.status == TransactionStatus.PENDING.value), Decimal("0"))
        remaining = policy.premium - policy.paid_total() - pending
        if remaining <= 0:
            raise Conflict("Премия по договору уже оплачена или ожидает подтверждения")
        amount = amount if amount is not None else remaining
        if amount > remaining:
            raise Unprocessable(f"Сумма платежа {amount} превышает неоплаченный остаток {remaining}")
        transaction = Transaction(policy_id=policy.policy_id, amount=amount,
                                  payment_date=datetime.now(), status=TransactionStatus.PENDING.value)
        self.session.add(transaction)
        self.session.commit()
        return transaction

    def get_transaction(self, transaction_id: int) -> Transaction:
        transaction = self.session.get(Transaction, transaction_id)
        if transaction is None:
            raise NotFound(f"Платёж {transaction_id} не найден")
        return transaction

    def list_payments(self, policy_id: int) -> list[Transaction]:
        return list(self.get(policy_id).transactions)

    def confirm_payment(self, transaction_id: int) -> Transaction:
        """Подтверждение платежа через банк; успешный платёж публикуется наблюдателям."""
        transaction = self.get_transaction(transaction_id)
        if transaction.status != TransactionStatus.PENDING.value:
            raise Conflict(f"Платёж уже обработан (статус {transaction.status})")
        policy = transaction.policy
        result = self.gateway.charge(policy.policy_number, transaction.amount)
        transaction.status = result.value
        if result == TransactionStatus.COMPLETED:
            self.publisher.publish(PaymentConfirmed(transaction, policy))
        self.session.commit()
        return transaction
