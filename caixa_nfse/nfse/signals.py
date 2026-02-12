"""
NFS-e signals — Auto-emissão de NFS-e ao confirmar MovimentoCaixa.

Disparado via post_save quando:
1. gerar_nfse_ao_confirmar está ativo no ConfiguracaoNFSe do tenant
2. Movimento tem cliente vinculado
3. Movimento ainda não tem nota_fiscal vinculada
"""

import logging

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender="caixa.MovimentoCaixa")
def auto_emitir_nfse(sender, instance, created, **kwargs):
    """
    Auto-emit NFS-e when a MovimentoCaixa is saved,
    if the tenant has gerar_nfse_ao_confirmar enabled.
    """
    if not created:
        return

    if instance.nota_fiscal_id:
        return

    if not instance.cliente_id:
        return

    if not _deve_gerar_nfse(instance.tenant):
        return

    from caixa_nfse.nfse.tasks import emitir_nfse_movimento

    mov_id = str(instance.pk)
    transaction.on_commit(lambda: emitir_nfse_movimento.delay(mov_id))

    logger.info(
        "Auto-emissão NFS-e agendada para movimento %s",
        instance.pk,
    )


def _deve_gerar_nfse(tenant):
    """Check if tenant has auto NFS-e generation enabled."""
    from caixa_nfse.nfse.models import ConfiguracaoNFSe

    try:
        config = ConfiguracaoNFSe.objects.get(tenant=tenant)
    except ConfiguracaoNFSe.DoesNotExist:
        return False

    return config.gerar_nfse_ao_confirmar
