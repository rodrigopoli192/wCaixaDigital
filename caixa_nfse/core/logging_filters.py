"""
Logging filter that injects request context (request_id, tenant_id, user_id)
into every log record for structured observability.
"""

import logging
import threading

_request_context = threading.local()


def set_request_context(*, request_id: str, user_id: str, tenant_id: str) -> None:
    """Set context for the current thread (called by middleware)."""
    _request_context.request_id = request_id
    _request_context.user_id = user_id
    _request_context.tenant_id = tenant_id


def clear_request_context() -> None:
    """Clear context after request completes."""
    for attr in ("request_id", "user_id", "tenant_id"):
        try:
            delattr(_request_context, attr)
        except AttributeError:
            pass


class RequestContextFilter(logging.Filter):
    """Adds request_id, tenant_id, user_id to every log record."""

    def filter(self, record):
        record.request_id = getattr(_request_context, "request_id", "-")
        record.tenant_id = getattr(_request_context, "tenant_id", "-")
        record.user_id = getattr(_request_context, "user_id", "-")
        return True
