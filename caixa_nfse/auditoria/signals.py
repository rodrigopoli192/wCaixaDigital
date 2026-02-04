"""
Auditoria signals - Automatic audit logging.
"""

from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .middleware import get_current_request
from .models import AcaoAuditoria, RegistroAuditoria

# Models to audit automatically
AUDITED_MODELS = [
    "caixa_nfse.core.Tenant",
    "caixa_nfse.core.User",
    "caixa_nfse.core.FormaPagamento",
    "caixa_nfse.caixa.Caixa",
    "caixa_nfse.caixa.AberturaCaixa",
    "caixa_nfse.caixa.MovimentoCaixa",
    "caixa_nfse.caixa.FechamentoCaixa",
    "caixa_nfse.clientes.Cliente",
    "caixa_nfse.nfse.NotaFiscalServico",
    "caixa_nfse.contabil.LancamentoContabil",
]


def model_to_dict(instance) -> dict:
    """Convert model instance to dictionary for audit."""
    data = {}
    for field in instance._meta.fields:
        value = getattr(instance, field.name)
        # Handle special types
        if hasattr(value, "pk"):
            value = str(value.pk)
        elif hasattr(value, "isoformat"):
            value = value.isoformat()
        elif isinstance(value, bytes):
            value = "[BINARY DATA]"
        else:
            value = str(value) if value is not None else None
        data[field.name] = value
    return data


def should_audit(sender) -> bool:
    """Check if model should be audited."""
    model_path = f"{sender._meta.app_label}.{sender.__name__}"
    return f"caixa_nfse.{model_path}" in AUDITED_MODELS


@receiver(pre_save)
def store_original_state(sender, instance, **kwargs):
    """Store original state before save for comparison."""
    if not should_audit(sender):
        return

    if instance.pk:
        try:
            original = sender.objects.get(pk=instance.pk)
            instance._audit_original = model_to_dict(original)
        except sender.DoesNotExist:
            instance._audit_original = None
    else:
        instance._audit_original = None


@receiver(post_save)
def audit_save(sender, instance, created, **kwargs):
    """Create audit record after save."""
    if not should_audit(sender):
        return

    # Skip if this is the RegistroAuditoria model itself
    if sender.__name__ == "RegistroAuditoria":
        return

    request = get_current_request()
    acao = AcaoAuditoria.CREATE if created else AcaoAuditoria.UPDATE

    dados_antes = getattr(instance, "_audit_original", None)
    dados_depois = model_to_dict(instance)

    # Only create audit record if there are actual changes
    if not created and dados_antes == dados_depois:
        return

    try:
        RegistroAuditoria.registrar(
            tabela=sender.__name__,
            registro_id=str(instance.pk),
            acao=acao,
            request=request,
            dados_antes=dados_antes,
            dados_depois=dados_depois,
        )
    except Exception:
        # Don't fail the main operation if audit fails
        import logging

        logging.getLogger(__name__).exception("Failed to create audit record")


@receiver(post_delete)
def audit_delete(sender, instance, **kwargs):
    """Create audit record after delete."""
    if not should_audit(sender):
        return

    request = get_current_request()
    dados_antes = model_to_dict(instance)

    try:
        RegistroAuditoria.registrar(
            tabela=sender.__name__,
            registro_id=str(instance.pk),
            acao=AcaoAuditoria.DELETE,
            request=request,
            dados_antes=dados_antes,
        )
    except Exception:
        import logging

        logging.getLogger(__name__).exception("Failed to create audit record")
