from functools import wraps

from .models import AcaoAuditoria, RegistroAuditoria


def audit_action(acao=AcaoAuditoria.VIEW, justificativa_template=""):
    """
    Decorator to audit custom controller actions (e.g. Export PDF).

    Usage:
    @audit_action(acao=AcaoAuditoria.EXPORT, justificativa_template="Exportou relatório {id}")
    def export_view(request, id): ...
    """

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            response = view_func(request, *args, **kwargs)

            # Log only on success (2xx)
            if 200 <= response.status_code < 300:
                try:
                    # Format msg with kwargs
                    msg = (
                        justificativa_template.format(**kwargs)
                        if justificativa_template
                        else f"Ação: {view_func.__name__}"
                    )

                    RegistroAuditoria.registrar(
                        tabela="CUSTOM",
                        registro_id="0",
                        acao=acao,
                        request=request,
                        justificativa=msg,
                        dados_antes={"view_args": args, "view_kwargs": kwargs},
                    )
                except Exception:
                    pass  # Don't break response

            return response

        return _wrapped_view

    return decorator
