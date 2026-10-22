import os

from fastapi import FastAPI

from common.db import make_engine, make_session_factory
from common.errors import install_error_handlers
from common.observability import health_router, install_request_id

from .api import router
from .models import Base
from .service import ProductService


def create_app(database_url: str | None = None, seed: bool = True) -> FastAPI:
    url = database_url or os.getenv("PRODUCT_DB_URL", "sqlite:///data/product.db")
    engine = make_engine(url)
    Base.metadata.create_all(engine)

    app = FastAPI(title="Insurance Product Service", version="0.1.0")
    app.state.session_factory = make_session_factory(engine)
    if seed:
        with app.state.session_factory() as session:
            ProductService(session).seed_if_empty()
    install_error_handlers(app)
    install_request_id(app, "product-service")
    app.include_router(health_router("product-service"))
    app.include_router(router)
    return app
