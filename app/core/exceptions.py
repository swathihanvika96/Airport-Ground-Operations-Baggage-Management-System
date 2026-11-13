"""Domain exceptions translated to HTTP responses by the central error handler."""
from typing import Any


class AppException(Exception):
    status_code: int = 400
    code: str = "APP_ERROR"

    def __init__(self, message: str, details: Any = None, code: str | None = None):
        super().__init__(message)
        self.message = message
        self.details = details
        if code:
            self.code = code


class NotFoundError(AppException):
    status_code = 404
    code = "NOT_FOUND"

    def __init__(self, entity: str, entity_id: Any = None):
        msg = f"{entity} not found" if entity_id is None else f"{entity} with id '{entity_id}' not found"
        super().__init__(msg)


class ConflictError(AppException):
    status_code = 409
    code = "CONFLICT"


class BusinessRuleError(AppException):
    status_code = 400
    code = "BUSINESS_RULE_VIOLATION"


class InvalidTransitionError(BusinessRuleError):
    code = "INVALID_STATUS_TRANSITION"

    def __init__(self, entity: str, current: Any, target: Any, allowed: Any = None):
        cur = getattr(current, "value", current)
        tgt = getattr(target, "value", target)
        super().__init__(
            f"Invalid {entity} status transition: {cur} -> {tgt}",
            details={"current": cur, "target": tgt,
                     "allowed": sorted(getattr(a, "value", a) for a in (allowed or []))},
        )


class AuthenticationError(AppException):
    status_code = 401
    code = "AUTHENTICATION_FAILED"


class PermissionDeniedError(AppException):
    status_code = 403
    code = "PERMISSION_DENIED"
