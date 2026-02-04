"""
Auditoria middleware - Capture request context for audit.
"""

import threading

_request_local = threading.local()


def get_current_request():
    """Get the current request from thread local storage."""
    return getattr(_request_local, "request", None)


class AuditMiddleware:
    """
    Middleware to store request in thread local for audit logging.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _request_local.request = request

        try:
            # Audit view access (GET requests only, ignoring static/admin assets)
            if request.method == "GET" and request.user.is_authenticated:
                path = request.path
                if not any(
                    path.startswith(p)
                    for p in [
                        "/static/",
                        "/media/",
                        "/admin/jsi18n/",
                        "/__debug__/",
                        "/favicon.ico",
                    ]
                ):
                    from .models import AcaoAuditoria, RegistroAuditoria

                    # Run in background or try/except to not block response
                    try:
                        RegistroAuditoria.registrar(
                            tabela="VIEW",
                            registro_id="0",
                            acao=AcaoAuditoria.VIEW,
                            request=request,
                            justificativa=f"Acesso à tela: {path}",
                            dados_antes={"query_params": dict(request.GET)},
                        )
                    except Exception:
                        # Fail silently for audit logging to not break app
                        pass

            response = self.get_response(request)
        finally:
            # Clean up
            if hasattr(_request_local, "request"):
                del _request_local.request

        return response
