"""
Middleware that sets request context for structured logging.
Populates request_id, user_id, tenant_id on each request.
"""

import uuid

from caixa_nfse.core.logging_filters import clear_request_context, set_request_context


class RequestLoggingMiddleware:
    """Populate thread-local request context and set X-Request-ID header."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = str(uuid.uuid4())[:8]
        user = getattr(request, "user", None)
        user_id = str(user.pk) if user and user.is_authenticated else "-"
        tenant_id = str(getattr(user, "tenant_id", "-")) if user else "-"

        set_request_context(
            request_id=request_id,
            user_id=user_id,
            tenant_id=tenant_id,
        )

        response = self.get_response(request)
        response["X-Request-ID"] = request_id

        clear_request_context()
        return response
