from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from common.errors import Conflict, NotFound, Unprocessable

from .builder import ClaimBuilder
from .enums import ClaimStatus, PayoutStatus
from .models import Claim, Payout
from .policy_directory import PolicyDirectory
from .schemas import ClaimCreate, ClaimUpdate, PayoutCreate
from .strategy import strategy_for


class ClaimService:
    """Регистрация и рассмотрение страховых случаев, создание и исполнение выплат."""

    def __init__(self, session: Session, policies: PolicyDirectory):
        self.session = session
        self.policies = policies

    # ---- страховые случаи
    def register(self, data: ClaimCreate) -> Claim:
        builder = (ClaimBuilder.for_policy(data.policy_id).event_date(data.event_date)
                   .description(data.description).damage_amount(data.damage_amount))
        for document in data.documents:
            builder.add_document(document)
        claim = builder.build()

        coverage = self.policies.coverage(data.policy_id, data.event_date)
        if not coverage.covered:
            raise Unprocessable(f"Страховой случай нельзя зарегистрировать: {coverage.reason}")
        self.session.add(claim)
        self.session.commit()
        return claim

    def get(self, claim_id: int) -> Claim:
        claim = self.session.get(Claim, claim_id)
        if claim is None:
            raise NotFound(f"Страховой случай {claim_id} не найден")
        return claim

    def list(self, policy_id: int | None, status: ClaimStatus | None) -> list[Claim]:
        stmt = select(Claim).order_by(Claim.claim_id)
        if policy_id is not None:
            stmt = stmt.where(Claim.policy_id == policy_id)
        if status is not None:
            stmt = stmt.where(Claim.status == status.value)
        return list(self.session.scalars(stmt))

    def update(self, claim_id: int, data: ClaimUpdate) -> Claim:
        claim = self.get(claim_id)
        if claim.status not in (ClaimStatus.CREATED.value, ClaimStatus.IN_REVIEW.value):
            raise Conflict(f"Случай в статусе {claim.status} изменять нельзя")
        if data.description is not None:
            claim.description = data.description
        if data.documents is not None:
            claim.documents = data.documents
        if data.damage_amount is not None:
            claim.damage_amount = data.damage_amount
        self.session.commit()
        return claim

    def transition(self, claim_id: int, action: str) -> Claim:
        claim = self.get(claim_id)
        getattr(claim, action)()  # start_review / approve / reject / close — через паттерн State
        self.session.commit()
        return claim

    # ---- выплаты
    def create_payout(self, data: PayoutCreate) -> Payout:
        claim = self.get(data.claim_id)
        if claim.status != ClaimStatus.APPROVED.value:
            raise Conflict(f"Выплата возможна только по одобренному случаю, а не {claim.status}")
        if self.session.scalar(select(Payout.payout_id).where(Payout.claim_id == claim.claim_id)):
            raise Conflict(f"По случаю {claim.claim_id} выплата уже создана")

        coverage = self.policies.coverage(claim.policy_id, claim.event_date)
        if not coverage.covered:
            raise Unprocessable(f"Выплата невозможна: {coverage.reason}")
        strategy = strategy_for(data.rule, data.deductible, data.actual_value)
        amount = strategy.calculate(claim.damage_amount, coverage.insured_amount)
        payout = Payout(claim_id=claim.claim_id, client_id=coverage.client_id, amount=amount,
                        rule=strategy.describe())
        self.session.add(payout)
        self.session.commit()
        return payout

    def get_payout(self, payout_id: int) -> Payout:
        payout = self.session.get(Payout, payout_id)
        if payout is None:
            raise NotFound(f"Выплата {payout_id} не найдена")
        return payout

    def approve_payout(self, payout_id: int) -> Payout:
        payout = self.get_payout(payout_id)
        if payout.status != PayoutStatus.CREATED.value:
            raise Conflict(f"Согласовать можно только выплату в статусе CREATED, а не {payout.status}")
        payout.status = PayoutStatus.APPROVED.value
        self.session.commit()
        return payout

    def execute_payout(self, payout_id: int) -> Payout:
        """Фиксация факта выплаты: статус PAID, дата выплаты, закрытие страхового случая."""
        payout = self.get_payout(payout_id)
        if payout.status != PayoutStatus.APPROVED.value:
            raise Conflict(f"Выплатить можно только согласованную выплату, а не {payout.status}")
        payout.status = PayoutStatus.PAID.value
        payout.paid_at = datetime.now()
        self.get(payout.claim_id).close()
        self.session.commit()
        return payout
