import os

from fastapi import FastAPI

from common.db import make_engine, make_session_factory
from common.errors import install_error_handlers
from common.observability import health_router, install_request_id
from common.resilience import ServiceClient

from .api import claims, payouts
from .models import Base
from .policy_directory import PolicyDirectory


def create_app(database_url: str | None = None, policy_service_url: str | None = None) -> FastAPI:
    url = database_url or os.getenv("CLAIM_DB_URL", "sqlite:///data/claim.db")
    engine = make_engine(url)
    Base.metadata.create_all(engine)

    app = FastAPI(title="Claim Service", version="0.1.0")
    app.state.session_factory = make_session_factory(engine)
    app.state.policies = PolicyDirectory(ServiceClient(
        "policy-service", policy_service_url or os.getenv("POLICY_SERVICE_URL", "http://127.0.0.1:8003")))
    install_error_handlers(app)
    install_request_id(app, "claim-service")
    app.include_router(health_router("claim-service"))
    app.include_router(claims)
    app.include_router(payouts)
    return app
