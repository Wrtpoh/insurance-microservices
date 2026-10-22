"""Обращения Policy Service к Client Service и Insurance Product Service (предметная связанность)."""
from common.errors import NotFound
from common.resilience import ServiceClient


class ClientDirectory:
    def __init__(self, client: ServiceClient):
        self._client = client

    def ensure_exists(self, client_id: int) -> None:
        response = self._client.get(f"/clients/{client_id}")
        if response.status_code == 404:
            raise NotFound(f"Клиент {client_id} не найден")


class ProductCatalog:
    def __init__(self, client: ServiceClient):
        self._client = client

    def get_product(self, product_id: int) -> dict:
        response = self._client.get(f"/products/{product_id}")
        if response.status_code == 404:
            raise NotFound(f"Страховой продукт {product_id} не найден")
        return response.json()
