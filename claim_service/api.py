from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from common.db import get_session

from .enums import ClaimStatus
from .schemas import ClaimCreate, ClaimOut, ClaimUpdate, PayoutCreate, PayoutOut
from .service import ClaimService

claims = APIRouter(prefix="/claims", tags=["claims"])
payouts = APIRouter(prefix="/payouts", tags=["payouts"])


def service(request: Request, session: Session = Depends(get_session)) -> ClaimService:
    return ClaimService(session, request.app.state.policies)


@claims.post("", response_model=ClaimOut, status_code=201)
def register_claim(data: ClaimCreate, svc: ClaimService = Depends(service)):
    return svc.register(data)


@claims.get("", response_model=list[ClaimOut])
def list_claims(policy_id: int | None = None, status: ClaimStatus | None = None,
                svc: ClaimService = Depends(service)):
    return svc.list(policy_id, status)


@claims.get("/{claim_id}", response_model=ClaimOut)
def get_claim(claim_id: int, svc: ClaimService = Depends(service)):
    return svc.get(claim_id)


@claims.put("/{claim_id}", response_model=ClaimOut)
def update_claim(claim_id: int, data: ClaimUpdate, svc: ClaimService = Depends(service)):
    return svc.update(claim_id, data)


@claims.post("/{claim_id}/review", response_model=ClaimOut)
def review_claim(claim_id: int, svc: ClaimService = Depends(service)):
    return svc.transition(claim_id, "start_review")


@claims.post("/{claim_id}/approve", response_model=ClaimOut)
def approve_claim(claim_id: int, svc: ClaimService = Depends(service)):
    return svc.transition(claim_id, "approve")


@claims.post("/{claim_id}/reject", response_model=ClaimOut)
def reject_claim(claim_id: int, svc: ClaimService = Depends(service)):
    return svc.transition(claim_id, "reject")


@claims.post("/{claim_id}/close", response_model=ClaimOut)
def close_claim(claim_id: int, svc: ClaimService = Depends(service)):
    return svc.transition(claim_id, "close")


@payouts.post("", response_model=PayoutOut, status_code=201)
def create_payout(data: PayoutCreate, svc: ClaimService = Depends(service)):
    return svc.create_payout(data)


@payouts.get("/{payout_id}", response_model=PayoutOut)
def get_payout(payout_id: int, svc: ClaimService = Depends(service)):
    return svc.get_payout(payout_id)


@payouts.post("/{payout_id}/approve", response_model=PayoutOut)
def approve_payout(payout_id: int, svc: ClaimService = Depends(service)):
    return svc.approve_payout(payout_id)


@payouts.post("/{payout_id}/execute", response_model=PayoutOut)
def execute_payout(payout_id: int, svc: ClaimService = Depends(service)):
    return svc.execute_payout(payout_id)
