"""ПАТТЕРН: Facade (структурный).

Оформление договора затрагивает Client Service, Insurance Product Service, фабрику договоров,
расчёт премии и сохранение. API вызывает один метод issue(), не зная об этих шагах.
"""
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from common.errors import Conflict

from .directories import ClientDirectory, ProductCatalog
from .factory import factory_for
from .models import Policy
from .premium import PremiumCalculator, PremiumRequest, default_calculator
from .schemas import PolicyCreate


class PolicyIssuanceFacade:
    def __init__(self, session: Session, clients: ClientDirectory, catalog: ProductCatalog,
                 calculator: PremiumCalculator | None = None):
        self._session = session
        self._clients = clients
        self._catalog = catalog
        self._calculator = calculator or default_calculator()

    def issue(self, data: PolicyCreate) -> Policy:
        self._clients.ensure_exists(data.client_id)
        product = self._catalog.get_product(data.product_id)
        if product["status"] != "ACTIVE":
            raise Conflict(f"Продукт «{product['name']}» недоступен для оформления")

        factory = factory_for(product["insurance_type"])
        policy = factory.issue(data.client_id, data.product_id, data.insured_amount,
                               data.start_date or date.today())
        policy.premium = self._calculator.calculate(PremiumRequest(
            insured_amount=data.insured_amount,
            base_rate=Decimal(product["base_rate"]),
            term_months=factory.term_months,
            claim_free_years=data.claim_free_years,
            high_risk_zone=data.high_risk_zone))

        self._session.add(policy)
        self._session.flush()  # получаем policy_id для номера договора
        factory.assign_number(policy)
        self._session.commit()
        return policy
