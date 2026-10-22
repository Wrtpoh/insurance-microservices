from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from common.errors import Conflict, NotFound

from .models import InsuranceType, Product, ProductStatus
from .schemas import ProductIn

SEED_PRODUCTS = [
    ("Автокаско", "Ущерб, угон и повреждение автомобиля", "0.0500", InsuranceType.AUTO),
    ("Медицинское страхование", "Добровольное медицинское страхование", "0.0300", InsuranceType.HEALTH),
    ("Страхование квартиры", "Имущество и гражданская ответственность", "0.0200", InsuranceType.PROPERTY),
]


class ProductService:
    """Каталог страховых продуктов и тарифов."""

    def __init__(self, session: Session):
        self.session = session

    def seed_if_empty(self) -> None:
        if self.session.scalar(select(func.count(Product.product_id))) == 0:
            for name, description, rate, kind in SEED_PRODUCTS:
                self.session.add(Product(name=name, description=description,
                                         base_rate=Decimal(rate), insurance_type=kind.value))
            self.session.commit()

    def _name_taken(self, name: str, except_id: int | None = None) -> bool:
        stmt = select(Product.product_id).where(Product.name == name)
        if except_id is not None:
            stmt = stmt.where(Product.product_id != except_id)
        return self.session.scalar(stmt) is not None

    def list(self, insurance_type: InsuranceType | None, status: ProductStatus | None) -> list[Product]:
        stmt = select(Product).order_by(Product.product_id)
        if insurance_type:
            stmt = stmt.where(Product.insurance_type == insurance_type.value)
        if status:
            stmt = stmt.where(Product.status == status.value)
        return list(self.session.scalars(stmt))

    def get(self, product_id: int) -> Product:
        product = self.session.get(Product, product_id)
        if product is None:
            raise NotFound(f"Страховой продукт {product_id} не найден")
        return product

    def create(self, data: ProductIn) -> Product:
        if self._name_taken(data.name):
            raise Conflict(f"Продукт «{data.name}» уже существует")
        product = Product(**{k: (v.value if hasattr(v, "value") else v) for k, v in data.model_dump().items()})
        self.session.add(product)
        self.session.commit()
        return product

    def update(self, product_id: int, data: ProductIn) -> Product:
        product = self.get(product_id)
        if self._name_taken(data.name, except_id=product_id):
            raise Conflict(f"Продукт «{data.name}» уже существует")
        for field, value in data.model_dump().items():
            setattr(product, field, value.value if hasattr(value, "value") else value)
        self.session.commit()
        return product
