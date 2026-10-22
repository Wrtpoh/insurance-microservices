from enum import StrEnum


class InsuranceType(StrEnum):
    AUTO = "AUTO"
    HEALTH = "HEALTH"
    PROPERTY = "PROPERTY"


class PolicyStatus(StrEnum):
    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class TransactionStatus(StrEnum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
