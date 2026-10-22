import os

from fastapi import FastAPI

from common.db import make_engine, make_session_factory
from common.errors import install_error_handlers
from common.observability import health_router, install_request_id

from .api import router
from .models import Base


def create_app(database_url: str | None = None) -> FastAPI:
    url = database_url or os.getenv("CLIENT_DB_URL", "sqlite:///data/client.db")
    engine = make_engine(url)
    Base.metadata.create_all(engine)

    app = FastAPI(title="Client Service", version="0.1.0")
    app.state.session_factory = make_session_factory(engine)
    install_error_handlers(app)
    install_request_id(app, "client-service")
    app.include_router(health_router("client-service"))
    app.include_router(router)
    return app
