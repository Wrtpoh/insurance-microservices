"""ПАТТЕРН: State (поведенческий).

Допустимые действия над страховым случаем зависят от статуса:
CREATED → IN_REVIEW → APPROVED / REJECTED → CLOSED. Каждое состояние само определяет разрешённые
переходы, недопустимые приводят к ошибке 409.
"""
from common.errors import Conflict

from .enums import ClaimStatus


class ClaimState:
    status: ClaimStatus

    def start_review(self, claim) -> None:
        self._denied(claim, "взять в работу")

    def approve(self, claim) -> None:
        self._denied(claim, "одобрить")

    def reject(self, claim) -> None:
        self._denied(claim, "отклонить")

    def close(self, claim) -> None:
        self._denied(claim, "закрыть")

    def _denied(self, claim, action: str):
        raise Conflict(f"Нельзя {action} страховой случай {claim.claim_id} в статусе {self.status.value}")


class CreatedState(ClaimState):
    status = ClaimStatus.CREATED

    def start_review(self, claim) -> None:
        claim.status = ClaimStatus.IN_REVIEW.value


class InReviewState(ClaimState):
    status = ClaimStatus.IN_REVIEW

    def approve(self, claim) -> None:
        if claim.damage_amount is None:
            raise Conflict(f"Нельзя одобрить случай {claim.claim_id}: не определена сумма ущерба")
        claim.status = ClaimStatus.APPROVED.value

    def reject(self, claim) -> None:
        claim.status = ClaimStatus.REJECTED.value


class ApprovedState(ClaimState):
    status = ClaimStatus.APPROVED

    def close(self, claim) -> None:
        claim.status = ClaimStatus.CLOSED.value


class RejectedState(ClaimState):
    status = ClaimStatus.REJECTED

    def close(self, claim) -> None:
        claim.status = ClaimStatus.CLOSED.value


class ClosedState(ClaimState):
    status = ClaimStatus.CLOSED


_STATES = {s.status.value: s() for s in
           (CreatedState, InReviewState, ApprovedState, RejectedState, ClosedState)}


def state_for(status: str) -> ClaimState:
    return _STATES[status]
