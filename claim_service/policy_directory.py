"""Обращение Claim Service к Policy Service: проверка договора на дату события."""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from common.errors import NotFound
from common.resilience import ServiceClient


@dataclass(frozen=True)
class Coverage:
    policy_id: int
    client_id: int
    insured_amount: Decimal
    covered: bool
    reason: str | None


class PolicyDirectory:
    def __init__(self, client: ServiceClient):
        self._client = client

    def coverage(self, policy_id: int, on_date: date) -> Coverage:
        response = self._client.get(f"/policies/{policy_id}/coverage", params={"on_date": on_date.isoformat()})
        if response.status_code == 404:
            raise NotFound(f"Договор {policy_id} не найден")
        data = response.json()
        return Coverage(data["policy_id"], data["client_id"], Decimal(data["insured_amount"]),
                        data["covered"], data.get("reason"))
