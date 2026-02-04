"""
NFS-e tasks - Celery tasks for async operations.
"""

import logging

from celery import shared_task

from .models import EventoFiscal, NotaFiscalServico, StatusNFSe, TipoEventoFiscal

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def enviar_nfse(self, nota_id: str) -> dict:
    """
    Envia NFS-e para prefeitura com retry automático.
    """
    try:
        nota = NotaFiscalServico.objects.get(pk=nota_id)

        # TODO: Implementar integração com WebService ABRASF
        # 1. Construir XML RPS
        # 2. Assinar XML com certificado digital
        # 3. Enviar para WebService
        # 4. Processar retorno

        # Placeholder - simula autorização
        logger.info(f"Enviando NFS-e {nota.numero_rps}...")

        # Registra evento
        EventoFiscal.objects.create(
            tenant=nota.tenant,
            nota=nota,
            tipo=TipoEventoFiscal.ENVIO,
            mensagem="Nota enviada para processamento (mock)",
            sucesso=True,
        )

        # Simula autorização
        nota.status = StatusNFSe.AUTORIZADA
        nota.numero_nfse = nota.numero_rps  # Em produção, viria do retorno
        nota.codigo_verificacao = "ABC123"  # Em produção, viria do retorno
        nota.save()

        EventoFiscal.objects.create(
            tenant=nota.tenant,
            nota=nota,
            tipo=TipoEventoFiscal.AUTORIZACAO,
            mensagem="Nota autorizada com sucesso (mock)",
            sucesso=True,
        )

        return {"success": True, "nota_id": str(nota.pk)}

    except NotaFiscalServico.DoesNotExist:
        logger.error(f"Nota {nota_id} não encontrada")
        return {"success": False, "error": "Nota não encontrada"}

    except Exception as e:
        logger.exception(f"Erro ao enviar NFS-e {nota_id}")
        self.retry(exc=e)


@shared_task
def verificar_certificados_vencendo() -> dict:
    """
    Verifica certificados digitais próximos do vencimento.
    Envia alertas para 30, 15 e 7 dias antes.
    """
    from datetime import timedelta

    from django.utils import timezone

    from caixa_nfse.core.models import Tenant

    hoje = timezone.now().date()
    alertas = []

    for dias in [30, 15, 7]:
        data_limite = hoje + timedelta(days=dias)
        tenants = Tenant.objects.filter(
            certificado_validade=data_limite,
            ativo=True,
        )

        for tenant in tenants:
            alertas.append(
                {
                    "tenant": tenant.razao_social,
                    "dias": dias,
                    "validade": str(tenant.certificado_validade),
                }
            )
            # TODO: Enviar e-mail de alerta
            logger.warning(f"Certificado de {tenant.razao_social} vence em {dias} dias")

    return {"alertas": alertas}


@shared_task
def consultar_lote_nfse(nota_ids: list[str]) -> dict:
    """
    Consulta status de lote de notas.
    """
    resultados = []

    for nota_id in nota_ids:
        try:
            nota = NotaFiscalServico.objects.get(pk=nota_id)
            resultados.append(
                {
                    "id": nota_id,
                    "status": nota.status,
                    "numero_nfse": nota.numero_nfse,
                }
            )
        except NotaFiscalServico.DoesNotExist:
            resultados.append(
                {
                    "id": nota_id,
                    "error": "Nota não encontrada",
                }
            )

    return {"resultados": resultados}
