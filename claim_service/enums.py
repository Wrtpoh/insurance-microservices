from enum import StrEnum


class ClaimStatus(StrEnum):
    CREATED = "CREATED"
    IN_REVIEW = "IN_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CLOSED = "CLOSED"


class PayoutStatus(StrEnum):
    CREATED = "CREATED"
    APPROVED = "APPROVED"
    PAID = "PAID"


class PayoutRule(StrEnum):
    FULL = "FULL"
    DEDUCTIBLE = "DEDUCTIBLE"
    PROPORTIONAL = "PROPORTIONAL"
