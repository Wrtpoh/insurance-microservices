"""Межсервисные вызовы: таймаут, Circuit Breaker, передача X-Request-ID."""
import time
from collections.abc import Callable

import httpx

from .errors import ServiceUnavailable
from .observability import REQUEST_ID_HEADER, current_request_id


class CircuitBreaker:
    """Автоматический выключатель: после N сбоёв подряд вызовы блокируются на reset_timeout секунд."""

    CLOSED, OPEN, HALF_OPEN = "closed", "open", "half_open"

    def __init__(self, failure_threshold: int = 3, reset_timeout: float = 10.0,
                 clock: Callable[[], float] = time.monotonic):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self._clock = clock
        self._failures = 0
        self._opened_at = 0.0
        self._state = self.CLOSED

    @property
    def state(self) -> str:
        if self._state == self.OPEN and self._clock() - self._opened_at >= self.reset_timeout:
            self._state = self.HALF_OPEN
        return self._state

    def allow(self) -> bool:
        return self.state != self.OPEN

    def record_success(self) -> None:
        self._failures = 0
        self._state = self.CLOSED

    def record_failure(self) -> None:
        self._failures += 1
        if self.state == self.HALF_OPEN or self._failures >= self.failure_threshold:
            self._state = self.OPEN
            self._opened_at = self._clock()


class ServiceClient:
    """HTTP-клиент другого сервиса. Ошибки 4xx возвращаются вызывающему, сбои сети и 5xx считаются отказом."""

    def __init__(self, name: str, base_url: str, timeout: float = 3.0,
                 breaker: CircuitBreaker | None = None, transport: httpx.BaseTransport | None = None):
        self.name = name
        self.breaker = breaker or CircuitBreaker()
        self._http = httpx.Client(base_url=base_url, timeout=timeout, transport=transport)

    def request(self, method: str, path: str, **kwargs) -> httpx.Response:
        if not self.breaker.allow():
            raise ServiceUnavailable(f"Сервис «{self.name}» временно недоступен (выключатель разомкнут)")
        headers = kwargs.pop("headers", {}) or {}
        headers.setdefault(REQUEST_ID_HEADER, current_request_id.get())
        try:
            response = self._http.request(method, path, headers=headers, **kwargs)
        except httpx.HTTPError as exc:
            self.breaker.record_failure()
            raise ServiceUnavailable(f"Сервис «{self.name}» недоступен: {exc.__class__.__name__}") from exc
        if response.status_code >= 500:
            self.breaker.record_failure()
            raise ServiceUnavailable(f"Сервис «{self.name}» вернул ошибку {response.status_code}")
        self.breaker.record_success()
        return response

    def get(self, path: str, **kwargs) -> httpx.Response:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs) -> httpx.Response:
        return self.request("POST", path, **kwargs)

    def close(self) -> None:
        self._http.close()
