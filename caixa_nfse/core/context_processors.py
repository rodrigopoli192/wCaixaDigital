"""
Context processors for core app.
"""

from django.db.models import Q


def tenant_context(request):
    """Add tenant information to template context."""
    context = {
        "current_tenant": None,
        "notificacoes_nao_lidas": 0,
    }

    if request.user.is_authenticated and hasattr(request.user, "tenant") and request.user.tenant:
        context["current_tenant"] = request.user.tenant

        from caixa_nfse.core.models import Notificacao

        context["notificacoes_nao_lidas"] = (
            Notificacao.objects.filter(
                tenant=request.user.tenant,
                lida=False,
            )
            .filter(Q(destinatario=request.user) | Q(destinatario__isnull=True))
            .count()
        )

    return context
