"""Интеграционное окружение: все сервисы и шлюз поднимаются в потоках на свободных портах,
у каждого сервиса своя БД SQLite во временной папке."""
import socket
import threading
import time
from dataclasses import dataclass

import httpx
import pytest
import uvicorn

from claim_service.main import create_app as create_claim
from client_service.main import create_app as create_client
from gateway.main import create_app as create_gateway
from policy_service.main import create_app as create_policy
from product_service.main import create_app as create_product


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Server:
    def __init__(self, app):
        self.port = free_port()
        self.server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=self.port, log_level="error"))
        self.thread = threading.Thread(target=self.server.run, daemon=True)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self) -> "Server":
        self.thread.start()
        for _ in range(100):
            if self.server.started:
                return self
            time.sleep(0.05)
        raise RuntimeError("сервер не запустился")

    def stop(self) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=5)


@dataclass
class Stack:
    api: httpx.Client          # запросы через шлюз
    client_url: str
    product_url: str
    policy_url: str
    claim_url: str
    secure_url: str            # шлюз с включённой авторизацией


@pytest.fixture(scope="session")
def stack(tmp_path_factory):
    db = tmp_path_factory.mktemp("db")
    client = Server(create_client(f"sqlite:///{db / 'client.db'}")).start()
    product = Server(create_product(f"sqlite:///{db / 'product.db'}")).start()
    policy = Server(create_policy(f"sqlite:///{db / 'policy.db'}", client.url, product.url)).start()
    claim = Server(create_claim(f"sqlite:///{db / 'claim.db'}", policy.url)).start()
    backends = {"client": client.url, "product": product.url, "policy": policy.url, "claim": claim.url}
    # шлюз без авторизации — для проверки бизнес-сценариев; шлюз с авторизацией — для проверки безопасности
    gateway = Server(create_gateway(backends, f"sqlite:///{db / 'gw_open.db'}", auth_enabled=False)).start()
    secure = Server(create_gateway(backends, f"sqlite:///{db / 'gw_secure.db'}", jwt_secret="test-secret")).start()
    with httpx.Client(base_url=f"{gateway.url}/api", timeout=10) as api:
        yield Stack(api, client.url, product.url, policy.url, claim.url, secure.url)
    for s in (secure, gateway, claim, policy, product, client):
        s.stop()


_phone = iter(range(9000000000, 9999999999))


@pytest.fixture
def new_client(stack):
    resp = stack.api.post("/clients", json={"full_name": "Иванов Иван Иванович", "phone": f"+7{next(_phone)}"})
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture
def active_policy(stack, new_client):
    """Оплаченный действующий договор автострахования."""
    policy = stack.api.post("/policies", json={"client_id": new_client["client_id"], "product_id": 1,
                                               "insured_amount": "500000"}).json()
    tx = stack.api.post(f"/policies/{policy['policy_id']}/payments", json={}).json()
    confirmed = stack.api.post(f"/payments/{tx['transaction_id']}/confirm").json()
    assert confirmed["status"] == "COMPLETED"
    return stack.api.get(f"/policies/{policy['policy_id']}").json()
