"""Аутентификация, права ролей и журнал действий на шлюзе с включённой авторизацией."""
import time
from datetime import date

import httpx
import pytest

from gateway.permissions import Role, allowed_roles
from gateway.security import create_token, decode_token, hash_password, verify_password
from common.errors import Unauthorized

PASSWORDS = {"admin": "admin123", "manager": "manager123", "agent": "agent123", "adjuster": "adjuster123"}


def login(stack, username: str) -> httpx.Client:
    resp = httpx.post(f"{stack.secure_url}/auth/login", json={"username": username,
                                                              "password": PASSWORDS[username]})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return httpx.Client(base_url=f"{stack.secure_url}/api", headers={"Authorization": f"Bearer {token}"},
                        timeout=10)


@pytest.fixture(scope="module")
def users(stack):
    clients = {name: login(stack, name) for name in PASSWORDS}
    yield clients
    for c in clients.values():
        c.close()


# ---- токены и пароли (юнит)
def test_password_hashing():
    stored = hash_password("секрет-123")
    assert verify_password("секрет-123", stored) and not verify_password("неверный", stored)


def test_token_roundtrip_tamper_and_expiry():
    token = create_token("s", "agent", "AGENT")
    assert decode_token("s", token)["role"] == "AGENT"
    with pytest.raises(Unauthorized):
        decode_token("другой-секрет", token)
    head, payload, sig = token.split(".")
    with pytest.raises(Unauthorized):
        decode_token("s", f"{head}.{payload}x.{sig}")
    with pytest.raises(Unauthorized, match="истёк"):
        decode_token("s", create_token("s", "agent", "AGENT", ttl_seconds=-1))


def test_permission_matrix_unit():
    assert allowed_roles("GET", "/policies/1") is None
    assert allowed_roles("POST", "/policies") == {Role.ADMIN, Role.AGENT}
    assert allowed_roles("POST", "/payouts/3/execute") == {Role.MANAGER}
    assert allowed_roles("DELETE", "/clients/1") == {Role.ADMIN}   # неописанное изменение — только админ


# ---- вход
def test_login_failures(stack):
    bad = httpx.post(f"{stack.secure_url}/auth/login", json={"username": "agent", "password": "wrong"})
    unknown = httpx.post(f"{stack.secure_url}/auth/login", json={"username": "nobody", "password": "x"})
    assert bad.status_code == unknown.status_code == 401
    assert bad.json()["error"]["message"] == unknown.json()["error"]["message"]


def test_requests_without_valid_token_are_rejected(stack):
    assert httpx.get(f"{stack.secure_url}/api/clients").status_code == 401
    bad = httpx.get(f"{stack.secure_url}/api/clients", headers={"Authorization": "Bearer abc.def.ghi"})
    assert bad.status_code == 401
    expired = create_token("test-secret", "agent", "AGENT", ttl_seconds=-5)
    assert httpx.get(f"{stack.secure_url}/api/clients",
                     headers={"Authorization": f"Bearer {expired}"}).status_code == 401


def test_me(users):
    resp =httpx.get(str(users["agent"].base_url).replace("/api/", "/auth/me"),
                     headers=users["agent"].headers)
    assert resp.json() == {"username": "agent", "role": "AGENT"}


# ---- права ролей
def test_role_permissions_on_clients_and_products(users):
    phone = f"+7{int(time.time() * 1000) % 10**10:010d}"
    client = {"full_name": "Сидоров Сидор", "phone": phone}
    assert users["adjuster"].post("/clients", json=client).status_code == 403
    assert users["manager"].post("/clients", json=client).status_code == 403
    assert users["agent"].post("/clients", json=client).status_code == 201
    assert users["adjuster"].get("/clients").status_code == 200          # просмотр доступен всем

    product = {"name": f"Продукт {phone}", "base_rate": "0.02", "insurance_type": "HEALTH"}
    assert users["agent"].post("/products", json=product).status_code == 403
    assert users["manager"].post("/products", json=product).status_code == 201


def test_full_business_flow_with_roles(users):
    agent, adjuster, manager = users["agent"], users["adjuster"], users["manager"]
    phone = f"+7{(int(time.time() * 1000) + 7) % 10**10:010d}"
    client = agent.post("/clients", json={"full_name": "Кузнецов Кузьма", "phone": phone}).json()
    policy = agent.post("/policies", json={"client_id": client["client_id"], "product_id": 1,
                                           "insured_amount": "500000"}).json()
    pid = policy["policy_id"]
    assert adjuster.post(f"/policies/{pid}/payments", json={}).status_code == 403   # платёж регистрирует агент
    tx = agent.post(f"/policies/{pid}/payments", json={}).json()
    assert manager.post(f"/payments/{tx['transaction_id']}/confirm").json()["status"] == "COMPLETED"

    claim = agent.post("/claims", json={"policy_id": pid, "event_date": date.today().isoformat(),
                                        "description": "ДТП", "damage_amount": "100000"}).json()
    cid = claim["claim_id"]
    assert agent.post(f"/claims/{cid}/review").status_code == 403                   # рассматривает специалист
    assert adjuster.post(f"/claims/{cid}/review").status_code == 200
    assert adjuster.post(f"/claims/{cid}/approve").status_code == 200
    payout = adjuster.post("/payouts", json={"claim_id": cid}).json()
    assert adjuster.post(f"/payouts/{payout['payout_id']}/approve").status_code == 403   # согласует руководитель
    assert manager.post(f"/payouts/{payout['payout_id']}/approve").status_code == 200
    assert manager.post(f"/payouts/{payout['payout_id']}/execute").json()["status"] == "PAID"


# ---- администрирование и журнал
def test_user_management_is_admin_only(stack, users):
    new = {"username": "agent2", "password": "StrongPass1", "full_name": "Агент Второй", "role": "AGENT"}
    base = stack.secure_url
    assert httpx.post(f"{base}/auth/users", json=new, headers=users["agent"].headers).status_code == 403
    created = httpx.post(f"{base}/auth/users", json=new, headers=users["admin"].headers)
    assert created.status_code == 201 and "password" not in created.json()
    assert httpx.post(f"{base}/auth/users", json=new, headers=users["admin"].headers).status_code == 409
    weak = {**new, "username": "agent3", "password": "123"}
    assert httpx.post(f"{base}/auth/users", json=weak, headers=users["admin"].headers).status_code == 422
    # новая учётная запись может войти
    assert httpx.post(f"{base}/auth/login", json={"username": "agent2", "password": "StrongPass1"}).status_code == 200


def test_audit_log_records_actions_for_admin_only(stack, users):
    users["agent"].post("/clients", json={"full_name": "Журнал Проверка", "phone": "+79990001122"})
    assert users["agent"].get("/audit").status_code == 403
    entries = users["admin"].get("/audit", params={"username": "agent"}).json()
    assert entries and entries[0]["username"] == "agent" and entries[0]["method"] == "POST"
    assert all(e["method"] != "GET" for e in entries)        # просмотр не журналируется
