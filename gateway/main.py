"""API Gateway: единая точка входа /api/<ресурс>/..., аутентификация (JWT), проверка прав по ролям,
журнал действий, маршрутизация в сервисы, Circuit Breaker и агрегированная проверка здоровья."""
import os

import httpx
from fastapi import Depends, FastAPI, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from common.db import get_session, make_engine, make_session_factory
from common.errors import Conflict, Forbidden, NotFound, Unauthorized, install_error_handlers
from common.observability import current_request_id, install_request_id
from common.resilience import ServiceClient

from .models import AuditEntry, Base, User
from .permissions import Role, allowed_roles
from .security import create_token, decode_token, hash_password, verify_password

# ресурс в URL -> сервис, которому он принадлежит
RESOURCE_OWNER = {
    "clients": "client", "products": "product",
    "policies": "policy", "payments": "policy",
    "claims": "claim", "payouts": "claim",
}
DEFAULT_URLS = {
    "client": "http://127.0.0.1:8001", "product": "http://127.0.0.1:8002",
    "policy": "http://127.0.0.1:8003", "claim": "http://127.0.0.1:8004",
}
# Учётные записи для первого запуска. Пароли — только для разработки: задайте свои через SEED_PASSWORD_<ЛОГИН>.
SEED_USERS = [("admin", "Администратор системы", Role.ADMIN), ("manager", "Руководитель", Role.MANAGER),
              ("agent", "Страховой агент", Role.AGENT), ("adjuster", "Специалист по убыткам", Role.ADJUSTER)]
STRIP_HEADERS = {"host", "content-length", "connection", "transfer-encoding", "authorization"}
METHODS = ["GET", "POST", "PUT", "DELETE"]


class LoginIn(BaseModel):
    username: str
    password: str


class UserIn(BaseModel):
    username: str = Field(pattern=r"^[a-z0-9_.-]{3,50}$")
    password: str = Field(min_length=8, max_length=100)
    full_name: str = Field(min_length=2, max_length=255)
    role: Role


class UserOut(BaseModel):
    username: str
    full_name: str
    role: Role
    active: bool


def seed_users(session: Session) -> None:
    if session.scalar(select(User.user_id).limit(1)) is not None:
        return
    for username, full_name, role in SEED_USERS:
        password = os.getenv(f"SEED_PASSWORD_{username.upper()}", f"{username}123")
        session.add(User(username=username, full_name=full_name, role=role.value,
                         password_hash=hash_password(password)))
    session.commit()


def create_app(service_urls: dict[str, str] | None = None, database_url: str | None = None,
               jwt_secret: str | None = None, auth_enabled: bool = True) -> FastAPI:
    urls = {name: (service_urls or {}).get(name) or os.getenv(f"{name.upper()}_SERVICE_URL", default)
            for name, default in DEFAULT_URLS.items()}
    clients = {name: ServiceClient(f"{name}-service", url) for name, url in urls.items()}
    secret = jwt_secret or os.getenv("JWT_SECRET", "dev-secret-change-me")

    engine = make_engine(database_url or os.getenv("GATEWAY_DB_URL", "sqlite:///data/gateway.db"))
    Base.metadata.create_all(engine)

    app = FastAPI(title="API Gateway", version="0.2.0")
    app.state.session_factory = make_session_factory(engine)
    with app.state.session_factory() as session:
        seed_users(session)
    install_error_handlers(app)
    install_request_id(app, "gateway")

    def authenticate(request: Request) -> dict:
        scheme, _, token = request.headers.get("Authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise Unauthorized("Требуется вход в систему (заголовок Authorization: Bearer <токен>)")
        return decode_token(secret, token)

    def require_admin(request: Request) -> dict:
        claims = authenticate(request)
        if claims["role"] != Role.ADMIN.value:
            raise Forbidden("Действие доступно только администратору")
        return claims

    # ---- здоровье
    @app.get("/health", tags=["health"])
    def health():
        report = {}
        for name, url in urls.items():
            try:
                body = httpx.get(f"{url}/health", timeout=1.5).json()
                report[name] = body.get("status", "unknown")
            except httpx.HTTPError:
                report[name] = "down"
        overall = "up" if all(v == "up" for v in report.values()) else "degraded"
        return {"service": "gateway", "status": overall, "services": report}

    # ---- аутентификация и учётные записи
    @app.post("/auth/login", tags=["auth"])
    def login(data: LoginIn, session: Session = Depends(get_session)):
        user = session.scalar(select(User).where(User.username == data.username))
        stored = user.password_hash if user else hash_password("dummy")  # одинаковое время ответа
        if not verify_password(data.password, stored) or user is None or not user.active:
            raise Unauthorized("Неверный логин или пароль")
        return {"access_token": create_token(secret, user.username, user.role), "token_type": "bearer",
                "expires_in": 3600, "role": user.role, "full_name": user.full_name}

    @app.get("/auth/me", tags=["auth"])
    def me(claims: dict = Depends(authenticate)):
        return {"username": claims["sub"], "role": claims["role"]}

    @app.get("/auth/users", response_model=list[UserOut], tags=["auth"])
    def list_users(_: dict = Depends(require_admin), session: Session = Depends(get_session)):
        return list(session.scalars(select(User).order_by(User.user_id)))

    @app.post("/auth/users", response_model=UserOut, status_code=201, tags=["auth"])
    def create_user(data: UserIn, _: dict = Depends(require_admin), session: Session = Depends(get_session)):
        if session.scalar(select(User.user_id).where(User.username == data.username)):
            raise Conflict(f"Пользователь {data.username} уже существует")
        user = User(username=data.username, full_name=data.full_name, role=data.role.value,
                    password_hash=hash_password(data.password))
        session.add(user)
        session.commit()
        return user

    # ---- журнал действий (до универсального маршрута!)
    @app.get("/api/audit", tags=["audit"])
    def audit(username: str | None = None, limit: int = Query(100, ge=1, le=500),
              _: dict = Depends(require_admin), session: Session = Depends(get_session)):
        stmt = select(AuditEntry).order_by(AuditEntry.entry_id.desc()).limit(limit)
        if username:
            stmt = stmt.where(AuditEntry.username == username)
        return [{"created_at": e.created_at, "username": e.username, "role": e.role, "method": e.method,
                 "path": e.path, "status_code": e.status_code, "request_id": e.request_id}
                for e in session.scalars(stmt)]

    def write_audit(claims: dict, method: str, path: str, status_code: int, request_id: str) -> None:
        with app.state.session_factory() as session:
            session.add(AuditEntry(username=claims["sub"], role=claims["role"], method=method,
                                   path=path[:300], status_code=status_code, request_id=request_id))
            session.commit()

    # ---- маршрутизация в сервисы
    @app.api_route("/api/{resource}", methods=METHODS, tags=["proxy"])
    @app.api_route("/api/{resource}/{path:path}", methods=METHODS, tags=["proxy"])
    async def proxy(resource: str, request: Request, path: str = ""):
        owner = RESOURCE_OWNER.get(resource)
        if owner is None:
            raise NotFound(f"Ресурс «{resource}» не существует")
        target = f"/{resource}" + (f"/{path}" if path else "")

        claims = None
        headers = {k: v for k, v in request.headers.items() if k.lower() not in STRIP_HEADERS}
        if auth_enabled:
            claims = authenticate(request)
            roles = allowed_roles(request.method, target)
            if roles is not None and claims["role"] not in roles:
                raise Forbidden(f"Роль {claims['role']} не может выполнить {request.method} {target}")
            headers["X-User"], headers["X-Role"] = claims["sub"], claims["role"]

        response = await run_in_threadpool(
            clients[owner].request, request.method, target, params=dict(request.query_params),
            content=await request.body(), headers=headers)
        if claims and request.method != "GET":
            await run_in_threadpool(write_audit, claims, request.method, target,
                                    response.status_code, current_request_id.get())
        return Response(content=response.content, status_code=response.status_code,
                        media_type=response.headers.get("content-type", "application/json"))

    return app
