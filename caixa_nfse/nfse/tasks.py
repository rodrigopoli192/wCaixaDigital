"""
NFS-e tasks - Celery tasks for async NFS-e operations.
"""

import logging

from celery import shared_task

from .backends.registry import get_backend
from .models import EventoFiscal, NotaFiscalServico, StatusNFSe, TipoEventoFiscal
from .services import criar_nfse_de_movimento

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def enviar_nfse(self, nota_id: str) -> dict:
    """
    Emite NFS-e via backend configurado (Strategy Pattern).

    1. Busca NotaFiscalServico
    2. Obtém backend via get_backend(tenant)
    3. Chama backend.emitir(nota, tenant)
    4. Atualiza nota com resultado
    """
    try:
        nota = NotaFiscalServico.objects.select_related("tenant").get(pk=nota_id)
        tenant = nota.tenant

        backend = get_backend(tenant)

        # Registra evento de envio
        EventoFiscal.objects.create(
            tenant=tenant,
            nota=nota,
            tipo=TipoEventoFiscal.ENVIO,
            mensagem=f"Enviando via {backend.__class__.__name__}",
            sucesso=True,
        )

        resultado = backend.emitir(nota, tenant)

        if resultado.sucesso:
            nota.status = StatusNFSe.AUTORIZADA
            nota.numero_nfse = resultado.numero_nfse or nota.numero_rps
            nota.codigo_verificacao = resultado.codigo_verificacao or ""
            nota.chave_acesso = resultado.chave_acesso or ""
            nota.protocolo = resultado.protocolo or ""
            nota.xml_nfse = resultado.xml_retorno or ""
            nota.pdf_url = resultado.pdf_url or ""
            nota.save()

            EventoFiscal.objects.create(
                tenant=tenant,
                nota=nota,
                tipo=TipoEventoFiscal.AUTORIZACAO,
                mensagem=resultado.mensagem or "Nota autorizada com sucesso",
                sucesso=True,
            )

            return {"success": True, "nota_id": str(nota.pk)}

        # Emissão rejeitada
        nota.status = StatusNFSe.REJEITADA
        nota.xml_nfse = resultado.xml_retorno or ""
        nota.save(update_fields=["status", "xml_nfse"])

        EventoFiscal.objects.create(
            tenant=tenant,
            nota=nota,
            tipo=TipoEventoFiscal.REJEICAO,
            mensagem=resultado.mensagem or "Emissão rejeitada",
            sucesso=False,
        )

        return {"success": False, "error": resultado.mensagem or "Emissão rejeitada"}

    except NotaFiscalServico.DoesNotExist:
        logger.error("Nota %s não encontrada", nota_id)
        return {"success": False, "error": "Nota não encontrada"}

    except Exception as e:
        logger.exception("Erro ao enviar NFS-e %s", nota_id)
        self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def emitir_nfse_movimento(self, movimento_id: str) -> dict:
    """
    Cria NFS-e a partir de um MovimentoCaixa e emite via backend.

    1. Busca MovimentoCaixa
    2. Cria NotaFiscalServico via services.criar_nfse_de_movimento
    3. Delega emissão para enviar_nfse
    """
    try:
        from caixa_nfse.caixa.models import MovimentoCaixa

        movimento = MovimentoCaixa.objects.select_related("tenant", "cliente").get(pk=movimento_id)

        # Se já tem nota vinculada, pula criação
        if movimento.nota_fiscal_id:
            logger.info(
                "Movimento %s já possui nota %s vinculada",
                movimento_id,
                movimento.nota_fiscal_id,
            )
            return enviar_nfse(str(movimento.nota_fiscal_id))

        nota = criar_nfse_de_movimento(movimento)

        return enviar_nfse(str(nota.pk))

    except MovimentoCaixa.DoesNotExist:
        logger.error("Movimento %s não encontrado", movimento_id)
        return {"success": False, "error": "Movimento não encontrado"}

    except ValueError as e:
        logger.warning("Não foi possível criar NFS-e: %s", e)
        return {"success": False, "error": str(e)}

    except Exception as e:
        logger.exception("Erro ao emitir NFS-e para movimento %s", movimento_id)
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
            logger.warning("Certificado de %s vence em %d dias", tenant.razao_social, dias)

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


@shared_task
def poll_nfse_status() -> dict:
    """
    Consulta status de notas em ENVIANDO há mais de 2 minutos.

    Atualiza status para AUTORIZADA ou REJEITADA quando o gateway
    confirma o processamento. Agenda via Celery Beat a cada 5 min.
    """
    from datetime import timedelta

    from django.utils import timezone

    cutoff = timezone.now() - timedelta(minutes=2)
    notas = NotaFiscalServico.objects.filter(
        status=StatusNFSe.ENVIANDO,
        updated_at__lt=cutoff,
    ).select_related("tenant")

    atualizadas = 0

    for nota in notas[:50]:  # Limit per run
        try:
            backend = get_backend(nota.tenant)
            resultado = backend.consultar(nota, nota.tenant)

            if not resultado.sucesso:
                continue

            status_raw = (resultado.status or "").lower()
            if status_raw in ("autorizada", "autorizado", "aut"):
                nota.status = StatusNFSe.AUTORIZADA
                nota.xml_nfse = resultado.xml_retorno or nota.xml_nfse
                nota.save(update_fields=["status", "xml_nfse", "updated_at"])

                EventoFiscal.objects.create(
                    tenant=nota.tenant,
                    nota=nota,
                    tipo=TipoEventoFiscal.AUTORIZACAO,
                    mensagem=f"Polling: {resultado.mensagem or 'Autorizada'}",
                    sucesso=True,
                )
                atualizadas += 1

            elif status_raw in ("rejeitada", "rejeitado", "erro"):
                nota.status = StatusNFSe.REJEITADA
                nota.xml_nfse = resultado.xml_retorno or nota.xml_nfse
                nota.save(update_fields=["status", "xml_nfse", "updated_at"])

                EventoFiscal.objects.create(
                    tenant=nota.tenant,
                    nota=nota,
                    tipo=TipoEventoFiscal.REJEICAO,
                    mensagem=f"Polling: {resultado.mensagem or 'Rejeitada'}",
                    sucesso=False,
                )
                atualizadas += 1

        except Exception:
            logger.exception("Erro polling nota %s", nota.pk)

    logger.info("poll_nfse_status: %d notas atualizadas", atualizadas)
    return {"atualizadas": atualizadas}
