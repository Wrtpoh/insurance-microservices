from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from common.db import get_session

from .facade import PolicyIssuanceFacade
from .schemas import CoverageOut, PaymentCreate, PolicyCreate, PolicyOut, TransactionOut
from .service import PolicyService

policies = APIRouter(prefix="/policies", tags=["policies"])
payments = APIRouter(prefix="/payments", tags=["payments"])


def service(request: Request, session: Session = Depends(get_session)) -> PolicyService:
    state = request.app.state
    return PolicyService(session, state.gateway, state.publisher)


def facade(request: Request, session: Session = Depends(get_session)) -> PolicyIssuanceFacade:
    state = request.app.state
    return PolicyIssuanceFacade(session, state.clients, state.catalog)


@policies.post("", response_model=PolicyOut, status_code=201)
def create_policy(data: PolicyCreate, f: PolicyIssuanceFacade = Depends(facade)):
    return f.issue(data)


@policies.get("", response_model=list[PolicyOut])
def list_policies(client_id: int | None = Query(None), svc: PolicyService = Depends(service)):
    return svc.list(client_id)


@policies.get("/{policy_id}", response_model=PolicyOut)
def get_policy(policy_id: int, svc: PolicyService = Depends(service)):
    return svc.get(policy_id)


@policies.get("/{policy_id}/coverage", response_model=CoverageOut)
def check_coverage(policy_id: int, on_date: date, svc: PolicyService = Depends(service)):
    return svc.coverage(policy_id, on_date)


@policies.post("/{policy_id}/activate", response_model=PolicyOut)
def activate_policy(policy_id: int, svc: PolicyService = Depends(service)):
    return svc.activate(policy_id)


@policies.post("/{policy_id}/renew", response_model=PolicyOut)
def renew_policy(policy_id: int, svc: PolicyService = Depends(service)):
    return svc.renew(policy_id)


@policies.post("/{policy_id}/cancel", response_model=PolicyOut)
def cancel_policy(policy_id: int, svc: PolicyService = Depends(service)):
    return svc.cancel(policy_id)


@policies.post("/{policy_id}/payments", response_model=TransactionOut, status_code=201)
def register_payment(policy_id: int, data: PaymentCreate, svc: PolicyService = Depends(service)):
    return svc.register_payment(policy_id, data.amount)


@policies.get("/{policy_id}/payments", response_model=list[TransactionOut])
def list_payments(policy_id: int, svc: PolicyService = Depends(service)):
    return svc.list_payments(policy_id)


@payments.get("/{transaction_id}", response_model=TransactionOut)
def get_payment(transaction_id: int, svc: PolicyService = Depends(service)):
    return svc.get_transaction(transaction_id)


@payments.post("/{transaction_id}/confirm", response_model=TransactionOut)
def confirm_payment(transaction_id: int, svc: PolicyService = Depends(service)):
    return svc.confirm_payment(transaction_id)
