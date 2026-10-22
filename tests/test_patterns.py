"""Юнит-тесты паттернов проектирования и устойчивости (без сети и БД)."""
from datetime import date
from decimal import Decimal

import pytest

from claim_service.builder import ClaimBuilder
from claim_service.enums import ClaimStatus, PayoutRule
from claim_service.strategy import strategy_for
from common.errors import Conflict, ServiceUnavailable, Unprocessable
from common.resilience import CircuitBreaker, ServiceClient
from policy_service.enums import PolicyStatus, TransactionStatus
from policy_service.events import EventPublisher, PaymentConfirmed, PolicyActivationListener
from policy_service.factory import factory_for
from policy_service.models import Policy, Transaction
from policy_service.payment_gateway import BankPaymentAdapter
from policy_service.premium import (BasePremiumCalculator, ClaimFreeDiscount, PremiumRequest,
                                    default_calculator)


def D(x):
    return Decimal(x)


# Factory Method
def test_factory_sets_term_and_number():
    auto = factory_for("AUTO").issue(1, 1, D("500000"), date(2026, 1, 1))
    prop = factory_for("PROPERTY").issue(1, 3, D("2000000"), date(2026, 1, 1))
    assert auto.end_date == date(2026, 12, 31)
    assert prop.end_date == date(2028, 12, 31)
    auto.policy_id = 7
    factory_for("AUTO").assign_number(auto)
    assert auto.policy_number == "POL-AUTO-000007"


def test_factory_rejects_amount_below_minimum():
    with pytest.raises(Unprocessable):
        factory_for("AUTO").issue(1, 1, D("1000"), date(2026, 1, 1))


# Decorator
def test_premium_decorators_chain():
    req = PremiumRequest(D("1000000"), D("0.02"), 36, claim_free_years=4, high_risk_zone=True)
    assert BasePremiumCalculator().calculate(req) == D("60000.00")
    assert ClaimFreeDiscount(BasePremiumCalculator()).calculate(req) == D("54000.00")
    assert default_calculator().calculate(req) == D("61560.00")  # 60000 * 0.9 * 1.2 * 0.95


def test_premium_without_discounts_equals_base():
    req = PremiumRequest(D("500000"), D("0.05"), 12)
    assert default_calculator().calculate(req) == D("25000.00")


# Adapter
def test_bank_adapter_maps_codes_to_statuses():
    gateway = BankPaymentAdapter()
    assert gateway.charge("POL-1", D("12500.50")) == TransactionStatus.COMPLETED
    assert gateway.charge("POL-1", D("2000000.00")) == TransactionStatus.FAILED


# Observer
def _policy_with_payment(amount: str):
    policy = Policy(policy_id=1, policy_number="POL-AUTO-000001", premium=D("1000"), is_paid=False,
                    status=PolicyStatus.CREATED.value)
    tx = Transaction(transaction_id=1, policy_id=1, amount=D(amount), status=TransactionStatus.COMPLETED.value)
    policy.transactions.append(tx)
    return policy, tx


def test_observer_activates_policy_when_fully_paid():
    publisher = EventPublisher()
    publisher.subscribe(PolicyActivationListener())
    policy, tx = _policy_with_payment("1000")
    publisher.publish(PaymentConfirmed(tx, policy))
    assert policy.is_paid and policy.status == PolicyStatus.ACTIVE.value


def test_observer_keeps_policy_inactive_on_partial_payment_and_supports_unsubscribe():
    publisher = EventPublisher()
    listener = PolicyActivationListener()
    publisher.subscribe(listener)
    policy, tx = _policy_with_payment("400")
    publisher.publish(PaymentConfirmed(tx, policy))
    assert not policy.is_paid and policy.status == PolicyStatus.CREATED.value
    publisher.unsubscribe(listener)
    policy2, tx2 = _policy_with_payment("1000")
    publisher.publish(PaymentConfirmed(tx2, policy2))
    assert not policy2.is_paid


# Builder
def test_builder_builds_valid_claim():
    claim = (ClaimBuilder.for_policy(5).event_date(date.today()).description("ДТП")
             .add_document("справка").add_document("фото").damage_amount(D("80000")).build())
    assert claim.documents == ["справка", "фото"] and claim.damage_amount == D("80000")


@pytest.mark.parametrize("build", [
    lambda: ClaimBuilder.for_policy(5).description("x").build(),
    lambda: ClaimBuilder.for_policy(5).event_date(date(2999, 1, 1)).description("x").build(),
    lambda: ClaimBuilder.for_policy(5).event_date(date.today()).description("  ").build(),
])
def test_builder_rejects_invalid_claim(build):
    with pytest.raises(Unprocessable):
        build()


# State
def _claim(damage=None):
    return ClaimBuilder.for_policy(5).event_date(date.today()).description("ДТП").damage_amount(damage).build()


def test_state_happy_path():
    claim = _claim(D("100"))
    claim.status = ClaimStatus.CREATED.value
    claim.start_review()
    claim.approve()
    claim.close()
    assert claim.status == ClaimStatus.CLOSED.value


def test_state_forbids_invalid_transitions():
    claim = _claim()
    claim.status = ClaimStatus.CREATED.value
    with pytest.raises(Conflict):
        claim.approve()
    claim.start_review()
    with pytest.raises(Conflict):
        claim.approve()  # не определён ущерб
    claim.reject()
    claim.close()
    with pytest.raises(Conflict):
        claim.start_review()


# Strategy
def test_payout_strategies():
    insured = D("200000")
    assert strategy_for(PayoutRule.FULL, None, None).calculate(D("300000"), insured) == D("200000.00")
    assert strategy_for(PayoutRule.DEDUCTIBLE, D("20000"), None).calculate(D("300000"), D("500000")) == D("280000.00")
    assert strategy_for(PayoutRule.PROPORTIONAL, None, D("750000")).calculate(D("300000"), D("500000")) == D("200000.00")


def test_strategy_requires_parameters():
    with pytest.raises(Unprocessable):
        strategy_for(PayoutRule.DEDUCTIBLE, None, None)


# Circuit Breaker
def test_circuit_breaker_opens_and_recovers():
    now = [0.0]
    breaker = CircuitBreaker(failure_threshold=2, reset_timeout=10, clock=lambda: now[0])
    assert breaker.allow()
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.state == CircuitBreaker.OPEN and not breaker.allow()
    now[0] = 11
    assert breaker.state == CircuitBreaker.HALF_OPEN and breaker.allow()
    breaker.record_success()
    assert breaker.state == CircuitBreaker.CLOSED


def test_service_client_opens_breaker_when_service_is_down():
    client = ServiceClient("dead", "http://127.0.0.1:1", timeout=0.3, breaker=CircuitBreaker(2, 60))
    for _ in range(2):
        with pytest.raises(ServiceUnavailable):
            client.get("/x")
    with pytest.raises(ServiceUnavailable, match="выключатель"):
        client.get("/x")
