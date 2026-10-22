"""Health Check и сквозной идентификатор запроса (упрощённая трассировка)."""
import contextvars
import logging
import uuid

from fastapi import APIRouter, FastAPI, Request
from sqlalchemy import text

REQUEST_ID_HEADER = "X-Request-ID"
current_request_id: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")

logger = logging.getLogger("insurance")


def install_request_id(app: FastAPI, service_name: str) -> None:
    """Каждому запросу присваивается X-Request-ID; он логируется и передаётся в вызовах других сервисов."""

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex[:12]
        token = current_request_id.set(request_id)
        try:
            response = await call_next(request)
        finally:
            current_request_id.reset(token)
        response.headers[REQUEST_ID_HEADER] = request_id
        logger.info("%s %s %s -> %s [%s]", service_name, request.method, request.url.path,
                    response.status_code, request_id)
        return response


def health_router(service_name: str) -> APIRouter:
    router = APIRouter(tags=["health"])

    @router.get("/health")
    def health(request: Request):
        db_status = "up"
        try:
            with request.app.state.session_factory() as session:
                session.execute(text("SELECT 1"))
        except Exception:  # noqa: BLE001 - любая ошибка означает недоступность БД
            db_status = "down"
        status = "up" if db_status == "up" else "degraded"
        return {"service": service_name, "status": status, "database": db_status}

    return router
