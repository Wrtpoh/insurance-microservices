"""Матрица прав из проектного решения (раздел «Роли и их полномочия»)."""
import re
from enum import StrEnum


class Role(StrEnum):
    ADMIN = "ADMIN"          # Администратор
    MANAGER = "MANAGER"      # Руководитель
    AGENT = "AGENT"          # Страховой агент
    ADJUSTER = "ADJUSTER"    # Специалист по убыткам


A, M, G, J = Role.ADMIN, Role.MANAGER, Role.AGENT, Role.ADJUSTER

# (методы, шаблон пути, роли). Просмотр данных (GET) доступен всем аутентифицированным ролям.
RULES: list[tuple[set[str], str, frozenset[Role]]] = [
    ({"POST", "PUT"}, r"/clients(/\d+)?", frozenset({A, G})),                      # данные клиентов
    ({"POST", "PUT"}, r"/products(/\d+)?", frozenset({A, M})),                     # продукты и тарифы
    ({"POST"}, r"/policies", frozenset({A, G})),                                   # оформление договора
    ({"POST"}, r"/policies/\d+/(activate|renew)", frozenset({A, G})),
    ({"POST"}, r"/policies/\d+/cancel", frozenset({M, G})),                        # отмена договора
    ({"POST"}, r"/policies/\d+/payments", frozenset({G})),                         # регистрация платежа
    ({"POST"}, r"/payments/\d+/confirm", frozenset({M, G})),                       # подтверждение оплаты
    ({"POST"}, r"/claims", frozenset({G, J})),                                     # регистрация случая
    ({"PUT"}, r"/claims/\d+", frozenset({G, J})),
    ({"POST"}, r"/claims/\d+/(review|approve|reject)", frozenset({J})),            # рассмотрение, решение
    ({"POST"}, r"/claims/\d+/close", frozenset({J, M})),
    ({"POST"}, r"/payouts", frozenset({J})),                                       # создание выплаты
    ({"POST"}, r"/payouts/\d+/(approve|execute)", frozenset({M})),                 # согласование, факт выплаты
]
_COMPILED = [(methods, re.compile(pattern), roles) for methods, pattern, roles in RULES]
ADMIN_ONLY = frozenset({A})


def allowed_roles(method: str, path: str) -> frozenset[Role] | None:
    """None — действие доступно любой аутентифицированной роли."""
    for methods, pattern, roles in _COMPILED:
        if method in methods and pattern.fullmatch(path):
            return roles
    if method in ("GET", "HEAD", "OPTIONS"):
        return None
    return ADMIN_ONLY  # неописанные изменяющие запросы — только администратор
