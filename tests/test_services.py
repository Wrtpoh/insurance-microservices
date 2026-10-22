"""Сквозные тесты: запросы идут через API Gateway к четырём сервисам со своими БД."""
from datetime import date, timedelta

import httpx

from claim_service.main import create_app as create_claim
from tests.conftest import Server


def test_gateway_health_reports_all_services(stack):
    assert stack.api.get("/clients").status_code == 200  # шлюз доступен
    gateway_url = str(stack.api.base_url).removesuffix("/api/")
    health = httpx.get(f"{gateway_url}/health").json()
    assert health["status"] == "up"
    assert set(health["services"]) == {"client", "product", "policy", "claim"}


def test_gateway_unknown_resource(stack):
    resp = stack.api.get("/unknown")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


# ---- Client Service
def test_client_crud_and_search(stack, new_client):
    cid = new_client["client_id"]
    assert stack.api.get(f"/clients/{cid}").json()["full_name"] == "Иванов Иван Иванович"
    updated = stack.api.put(f"/clients/{cid}", json={"full_name": "Иванов Иван", "phone": new_client["phone"],
                                                     "email": "ivan@example.com"})
    assert updated.status_code == 200 and updated.json()["email"] == "ivan@example.com"
    found = stack.api.get("/clients", params={"q": "иванов иван"}).json()
    assert cid in [c["client_id"] for c in found]


def test_client_duplicate_phone_and_validation(stack, new_client):
    dup = stack.api.post("/clients", json={"full_name": "Петров Пётр", "phone": new_client["phone"]})
    assert dup.status_code == 409
    bad = stack.api.post("/clients", json={"full_name": "Петров Пётр", "phone": "123"})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "validation_error"
    assert stack.api.get("/clients/999999").status_code == 404


# ---- Product Service
def test_products_seeded_and_filtered(stack):
    products = stack.api.get("/products").json()
    assert {p["insurance_type"] for p in products} >= {"AUTO", "HEALTH", "PROPERTY"}
    auto = stack.api.get("/products", params={"insurance_type": "AUTO"}).json()
    assert all(p["insurance_type"] == "AUTO" for p in auto)


def test_product_create_validation_and_conflict(stack):
    body = {"name": "ОСАГО-тест", "base_rate": "0.0150", "insurance_type": "AUTO"}
    assert stack.api.post("/products", json=body).status_code == 201
    assert stack.api.post("/products", json=body).status_code == 409
    assert stack.api.post("/products", json={**body, "name": "Другой", "base_rate": "1.5"}).status_code == 422


# ---- Policy Service
def test_policy_issue_calculates_premium(stack, new_client):
    resp = stack.api.post("/policies", json={"client_id": new_client["client_id"], "product_id": 1,
                                             "insured_amount": "500000", "claim_free_years": 3})
    assert resp.status_code == 201
    policy = resp.json()
    assert policy["premium"] == "22500.00"          # 500000 * 5% * скидка 10%
    assert policy["status"] == "CREATED" and policy["is_paid"] is False
    assert policy["policy_number"].startswith("POL-AUTO-")


def test_policy_issue_errors(stack, new_client):
    cid = new_client["client_id"]
    assert stack.api.post("/policies", json={"client_id": 999999, "product_id": 1,
                                             "insured_amount": "500000"}).status_code == 404
    assert stack.api.post("/policies", json={"client_id": cid, "product_id": 999,
                                             "insured_amount": "500000"}).status_code == 404
    assert stack.api.post("/policies", json={"client_id": cid, "product_id": 1,
                                             "insured_amount": "1000"}).status_code == 422


def test_inactive_product_cannot_be_issued(stack, new_client):
    product = stack.api.post("/products", json={"name": "Снят с продажи", "base_rate": "0.01",
                                                "insurance_type": "HEALTH", "status": "INACTIVE"}).json()
    resp = stack.api.post("/policies", json={"client_id": new_client["client_id"],
                                             "product_id": product["product_id"], "insured_amount": "100000"})
    assert resp.status_code == 409


def test_payment_flow_activates_policy(stack, active_policy):
    assert active_policy["is_paid"] is True and active_policy["status"] == "ACTIVE"
    payments = stack.api.get(f"/policies/{active_policy['policy_id']}/payments").json()
    assert [p["status"] for p in payments] == ["COMPLETED"]
    again = stack.api.post(f"/payments/{payments[0]['transaction_id']}/confirm")
    assert again.status_code == 409
    assert stack.api.post(f"/policies/{active_policy['policy_id']}/payments", json={}).status_code == 409


def test_partial_payments_and_overpayment(stack, new_client):
    policy = stack.api.post("/policies", json={"client_id": new_client["client_id"], "product_id": 1,
                                               "insured_amount": "400000"}).json()   # премия 20000
    pid = policy["policy_id"]
    assert stack.api.post(f"/policies/{pid}/payments", json={"amount": "30000"}).status_code == 422
    first = stack.api.post(f"/policies/{pid}/payments", json={"amount": "5000"}).json()
    stack.api.post(f"/payments/{first['transaction_id']}/confirm")
    assert stack.api.get(f"/policies/{pid}").json()["status"] == "CREATED"
    rest = stack.api.post(f"/policies/{pid}/payments", json={}).json()
    assert rest["amount"] == "15000.00"
    stack.api.post(f"/payments/{rest['transaction_id']}/confirm")
    assert stack.api.get(f"/policies/{pid}").json()["status"] == "ACTIVE"


def test_bank_failure_keeps_policy_unpaid(stack, new_client):
    big =stack.api.post("/policies", json={"client_id": new_client["client_id"], "product_id": 1,
                                            "insured_amount": "30000000"}).json()     # премия 1 500 000
    tx = stack.api.post(f"/policies/{big['policy_id']}/payments", json={}).json()
    result = stack.api.post(f"/payments/{tx['transaction_id']}/confirm").json()
    assert result["status"] == "FAILED"
    assert stack.api.get(f"/policies/{big['policy_id']}").json()["is_paid"] is False


def test_policy_lifecycle_renew_and_cancel(stack, active_policy):
    pid = active_policy["policy_id"]
    renewed = stack.api.post(f"/policies/{pid}/renew").json()
    assert renewed["end_date"] > active_policy["end_date"]
    assert stack.api.post(f"/policies/{pid}/cancel").json()["status"] == "CANCELLED"
    assert stack.api.post(f"/policies/{pid}/cancel").status_code == 409


def test_activate_requires_payment(stack, new_client):
    policy = stack.api.post("/policies", json={"client_id": new_client["client_id"], "product_id": 2,
                                               "insured_amount": "100000"}).json()
    assert stack.api.post(f"/policies/{policy['policy_id']}/activate").status_code == 409


# ---- Claim Service
def _claim_body(policy, **extra):
    return {"policy_id": policy["policy_id"], "event_date": date.today().isoformat(),
            "description": "Столкновение на парковке", "documents": ["справка ГИБДД"], **extra}


def test_claim_requires_paid_active_policy(stack, new_client):
    unpaid = stack.api.post("/policies", json={"client_id": new_client["client_id"], "product_id": 1,
                                               "insured_amount": "500000"}).json()
    resp = stack.api.post("/claims", json=_claim_body(unpaid))
    assert resp.status_code == 422 and "не оплачена" in resp.json()["error"]["message"]
    assert stack.api.post("/claims", json={**_claim_body(unpaid), "policy_id": 999999}).status_code == 404


def test_claim_event_outside_policy_period(stack, active_policy):
    resp = stack.api.post("/claims", json=_claim_body(
        active_policy, event_date=(date.today() - timedelta(days=400)).isoformat()))
    assert resp.status_code == 422 and "вне периода" in resp.json()["error"]["message"]
    future = stack.api.post("/claims", json=_claim_body(
        active_policy, event_date=(date.today() + timedelta(days=1)).isoformat()))
    assert future.status_code == 422


def test_full_claim_and_payout_flow(stack, active_policy):
    claim = stack.api.post("/claims", json=_claim_body(active_policy)).json()
    cid = claim["claim_id"]
    assert claim["status"] == "CREATED"
    assert stack.api.post(f"/claims/{cid}/approve").status_code == 409      # State: из CREATED нельзя
    assert stack.api.post(f"/payouts", json={"claim_id": cid}).status_code == 409

    assert stack.api.post(f"/claims/{cid}/review").json()["status"] == "IN_REVIEW"
    assert stack.api.post(f"/claims/{cid}/approve").status_code == 409      # нет суммы ущерба
    stack.api.put(f"/claims/{cid}", json={"damage_amount": "650000"})
    assert stack.api.post(f"/claims/{cid}/approve").json()["status"] == "APPROVED"

    payout = stack.api.post("/payouts", json={"claim_id": cid, "rule": "DEDUCTIBLE", "deductible": "50000"}).json()
    assert payout["amount"] == "500000.00"       # 650000 - 50000 = 600000, но не больше страховой суммы 500000
    assert payout["client_id"] == active_policy["client_id"] and payout["status"] == "CREATED"
    assert stack.api.post("/payouts", json={"claim_id": cid}).status_code == 409   # 1:1 с случаем

    pid = payout["payout_id"]
    assert stack.api.post(f"/payouts/{pid}/execute").status_code == 409    # сначала согласование
    assert stack.api.post(f"/payouts/{pid}/approve").json()["status"] == "APPROVED"
    paid = stack.api.post(f"/payouts/{pid}/execute").json()
    assert paid["status"] == "PAID" and paid["paid_at"] is not None
    assert stack.api.get(f"/claims/{cid}").json()["status"] == "CLOSED"


def test_rejected_claim_has_no_payout(stack, active_policy):
    cid = stack.api.post("/claims", json=_claim_body(active_policy)).json()["claim_id"]
    stack.api.post(f"/claims/{cid}/review")
    assert stack.api.post(f"/claims/{cid}/reject").json()["status"] == "REJECTED"
    assert stack.api.post("/payouts", json={"claim_id": cid}).status_code == 409
    assert stack.api.post(f"/claims/{cid}/close").json()["status"] == "CLOSED"
    assert stack.api.put(f"/claims/{cid}", json={"description": "x"}).status_code == 409


def test_payout_rule_parameters_are_validated(stack, active_policy):
    cid = stack.api.post("/claims", json=_claim_body(active_policy, damage_amount="100000")).json()["claim_id"]
    stack.api.post(f"/claims/{cid}/review")
    stack.api.post(f"/claims/{cid}/approve")
    assert stack.api.post("/payouts", json={"claim_id": cid, "rule": "PROPORTIONAL"}).status_code == 422


# ---- устойчивость
def test_claim_service_degrades_when_policy_service_is_down(tmp_path):
    claim = Server(create_claim(f"sqlite:///{tmp_path / 'c.db'}", "http://127.0.0.1:1")).start()
    try:
        resp = httpx.post(f"{claim.url}/claims", json={"policy_id": 1, "event_date": date.today().isoformat(),
                                                       "description": "ДТП"}, timeout=10)
        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "service_unavailable"
        assert httpx.get(f"{claim.url}/health").json()["status"] == "up"   # сам сервис жив
    finally:
        claim.stop()


def test_request_id_is_propagated(stack):
    resp = stack.api.get("/clients", headers={"X-Request-ID": "trace-123"})
    assert resp.headers["X-Request-ID"] == "trace-123"
