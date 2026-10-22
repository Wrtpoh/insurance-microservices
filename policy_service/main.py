import os

from fastapi import FastAPI

from common.db import make_engine, make_session_factory
from common.errors import install_error_handlers
from common.observability import health_router, install_request_id
from common.resilience import ServiceClient

from .api import payments, policies
from .directories import ClientDirectory, ProductCatalog
from .events import AuditLogListener, EventPublisher, PolicyActivationListener
from .models import Base
from .payment_gateway import BankPaymentAdapter, PaymentGateway


def create_app(database_url: str | None = None, client_service_url: str | None = None,
               product_service_url: str | None = None, gateway: PaymentGateway | None = None) -> FastAPI:
    url = database_url or os.getenv("POLICY_DB_URL", "sqlite:///data/policy.db")
    engine = make_engine(url)
    Base.metadata.create_all(engine)

    app = FastAPI(title="Policy Service", version="0.1.0")
    app.state.session_factory = make_session_factory(engine)
    app.state.clients = ClientDirectory(ServiceClient(
        "client-service", client_service_url or os.getenv("CLIENT_SERVICE_URL", "http://127.0.0.1:8001")))
    app.state.catalog = ProductCatalog(ServiceClient(
        "product-service", product_service_url or os.getenv("PRODUCT_SERVICE_URL", "http://127.0.0.1:8002")))
    app.state.gateway = gateway or BankPaymentAdapter()

    publisher = EventPublisher()
    publisher.subscribe(PolicyActivationListener())
    publisher.subscribe(AuditLogListener())
    app.state.publisher = publisher

    install_error_handlers(app)
    install_request_id(app, "policy-service")
    app.include_router(health_router("policy-service"))
    app.include_router(policies)
    app.include_router(payments)
    return app
