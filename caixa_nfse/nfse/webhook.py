"""
NFS-e Webhook — Endpoint para callbacks assíncronos dos gateways.

Recebe notificações de Focus NFe e TecnoSpeed quando o processamento
de uma NFS-e é concluído (autorizada, rejeitada, cancelada).

Endpoint público (sem auth Django), protegido por webhook_token.
"""

import json
import logging

from django.http import HttpResponse, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from .models import (
    ConfiguracaoNFSe,
    EventoFiscal,
    NotaFiscalServico,
    StatusNFSe,
    TipoEventoFiscal,
)

logger = logging.getLogger(__name__)

# Status mappings per gateway
FOCUS_STATUS_MAP = {
    "autorizado": StatusNFSe.AUTORIZADA,
    "autorizada": StatusNFSe.AUTORIZADA,
    "cancelado": StatusNFSe.CANCELADA,
    "cancelada": StatusNFSe.CANCELADA,
    "erro_autorizacao": StatusNFSe.REJEITADA,
    "rejeitado": StatusNFSe.REJEITADA,
}

TECNOSPEED_STATUS_MAP = {
    "autorizada": StatusNFSe.AUTORIZADA,
    "aut": StatusNFSe.AUTORIZADA,
    "cancelada": StatusNFSe.CANCELADA,
    "rejeitada": StatusNFSe.REJEITADA,
    "erro": StatusNFSe.REJEITADA,
}


def _validate_token(request):
    """Validate webhook token from header or query param."""
    token = request.headers.get("X-Webhook-Token") or request.GET.get("token") or ""
    if not token:
        return None

    config = ConfiguracaoNFSe.objects.filter(webhook_token=token).first()
    return config


def _find_nota(ref, tenant):
    """Find nota by ref (pk) or protocolo."""
    try:
        return NotaFiscalServico.objects.get(pk=ref, tenant=tenant)
    except (NotaFiscalServico.DoesNotExist, ValueError):
        pass

    nota = NotaFiscalServico.objects.filter(
        protocolo=ref,
        tenant=tenant,
    ).first()
    return nota


@method_decorator(csrf_exempt, name="dispatch")
class NFSeWebhookView(View):
    """Recebe callbacks assíncronos dos gateways NFS-e."""

    def post(self, request):
        config = _validate_token(request)
        if not config:
            logger.warning("Webhook: token inválido ou ausente")
            return JsonResponse(
                {"error": "Token inválido"},
                status=401,
            )

        try:
            payload = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse(
                {"error": "JSON inválido"},
                status=400,
            )

        tenant = config.tenant
        backend = config.backend or ""

        ref = str(payload.get("ref") or payload.get("id") or payload.get("referencia") or "")

        if not ref:
            return JsonResponse(
                {"error": "Referência da nota não informada"},
                status=400,
            )

        nota = _find_nota(ref, tenant)
        if not nota:
            logger.warning(
                "Webhook: nota não encontrada ref=%s tenant=%s",
                ref,
                tenant.pk,
            )
            return JsonResponse({"error": "Nota não encontrada"}, status=404)

        # Determine status based on gateway
        status_raw = (payload.get("status") or payload.get("situacao") or "").lower()

        if "focus" in backend:
            status_map = FOCUS_STATUS_MAP
        else:
            status_map = TECNOSPEED_STATUS_MAP

        new_status = status_map.get(status_raw)

        if new_status is None:
            logger.info(
                "Webhook: status '%s' não mapeado (nota %s)",
                status_raw,
                nota.pk,
            )
            return JsonResponse({"ok": True, "action": "ignored"})

        old_status = nota.status

        # Update nota fields
        nota.status = new_status

        if new_status == StatusNFSe.AUTORIZADA:
            nota.numero_nfse = payload.get("numero", payload.get("numero_nfse")) or nota.numero_nfse
            nota.codigo_verificacao = (
                payload.get("codigo_verificacao", "") or nota.codigo_verificacao
            )
            nota.xml_nfse = payload.get("xml", payload.get("xml_nfse", "")) or nota.xml_nfse
            nota.pdf_url = (
                payload.get("caminho_xml_nota_fiscal")
                or payload.get("link_pdf")
                or payload.get("url_pdf", "")
                or nota.pdf_url
            )
            nota.protocolo = payload.get("protocolo", "") or nota.protocolo

        nota.save()

        # Register EventoFiscal
        tipo_evento = {
            StatusNFSe.AUTORIZADA: TipoEventoFiscal.AUTORIZACAO,
            StatusNFSe.CANCELADA: TipoEventoFiscal.CANCELAMENTO,
            StatusNFSe.REJEITADA: TipoEventoFiscal.REJEICAO,
        }.get(new_status, TipoEventoFiscal.CONSULTA)

        mensagem = payload.get("mensagem", payload.get("motivo", ""))

        EventoFiscal.objects.create(
            tenant=tenant,
            nota=nota,
            tipo=tipo_evento,
            protocolo=payload.get("protocolo", ""),
            mensagem=f"Webhook {backend}: {old_status} → {new_status} | {mensagem}",
            sucesso=new_status != StatusNFSe.REJEITADA,
        )

        logger.info(
            "Webhook: nota %s atualizada %s → %s (ref=%s)",
            nota.pk,
            old_status,
            new_status,
            ref,
        )

        return JsonResponse({"ok": True, "nota_id": str(nota.pk), "status": new_status})

    def get(self, request):
        """Health check for webhook endpoint."""
        return HttpResponse("OK", content_type="text/plain")
