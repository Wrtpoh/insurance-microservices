from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from common.db import get_session

from .schemas import ClientIn, ClientOut
from .service import ClientService

router = APIRouter(prefix="/clients", tags=["clients"])


def service(session: Session = Depends(get_session)) -> ClientService:
    return ClientService(session)


@router.post("", response_model=ClientOut, status_code=201)
def create_client(data: ClientIn, svc: ClientService = Depends(service)):
    return svc.create(data)


@router.get("", response_model=list[ClientOut])
def search_clients(q: str | None = None, limit: int = Query(50, ge=1, le=200),
                   offset: int = Query(0, ge=0), svc: ClientService = Depends(service)):
    return svc.search(q, limit, offset)


@router.get("/{client_id}", response_model=ClientOut)
def get_client(client_id: int, svc: ClientService = Depends(service)):
    return svc.get(client_id)


@router.put("/{client_id}", response_model=ClientOut)
def update_client(client_id: int, data: ClientIn, svc: ClientService = Depends(service)):
    return svc.update(client_id, data)
