from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from common.db import get_session

from .models import InsuranceType, ProductStatus
from .schemas import ProductIn, ProductOut
from .service import ProductService

router = APIRouter(prefix="/products", tags=["products"])


def service(session: Session = Depends(get_session)) -> ProductService:
    return ProductService(session)


@router.get("", response_model=list[ProductOut])
def list_products(insurance_type: InsuranceType | None = None, status: ProductStatus | None = None,
                  svc: ProductService = Depends(service)):
    return svc.list(insurance_type, status)


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: int, svc: ProductService = Depends(service)):
    return svc.get(product_id)


@router.post("", response_model=ProductOut, status_code=201)
def create_product(data: ProductIn, svc: ProductService = Depends(service)):
    return svc.create(data)


@router.put("/{product_id}", response_model=ProductOut)
def update_product(product_id: int, data: ProductIn, svc: ProductService = Depends(service)):
    return svc.update(product_id, data)
