"""
Editar Saldo Inicial View - permite editar saldo_abertura uma vez por dia.
"""

import logging
from decimal import Decimal

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.utils import timezone
from django.views import View

from caixa_nfse.caixa.models import AberturaCaixa

logger = logging.getLogger(__name__)


class EditarSaldoInicialView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Editar saldo inicial de uma abertura (once-per-day)."""

    def test_func(self):
        return self.request.user.pode_operar_caixa

    def get(self, request, pk):
        """Retorna modal com form."""
        abertura = get_object_or_404(
            AberturaCaixa,
            pk=pk,
            tenant=request.user.tenant,
            operador=request.user,
        )
        if not abertura.pode_editar_saldo_inicial:
            return HttpResponse(
                '<div class="p-4 text-red-500 text-sm">Edição não permitida. '
                "O saldo inicial já foi editado ou o caixa está fechado.</div>"
            )

        html = render_to_string(
            "caixa/partials/modal_editar_saldo.html",
            {"abertura": abertura},
            request=request,
        )
        return HttpResponse(html)

    def post(self, request, pk):
        """Processa edição do saldo inicial."""
        abertura = get_object_or_404(
            AberturaCaixa,
            pk=pk,
            tenant=request.user.tenant,
            operador=request.user,
        )

        if not abertura.pode_editar_saldo_inicial:
            return HttpResponse(
                '<div class="p-3 text-red-500 text-sm">Edição não permitida.</div>',
                status=403,
            )

        novo_valor_str = request.POST.get("novo_saldo", "").replace(".", "").replace(",", ".")
        try:
            novo_valor = Decimal(novo_valor_str)
            if novo_valor < 0:
                raise ValueError("Valor negativo")
        except (ValueError, Exception):
            return HttpResponse(
                '<div class="p-3 text-red-500 text-sm">Valor inválido. Informe um número válido.</div>',
                status=400,
            )

        # Usar transação para garantir consistência
        with transaction.atomic():
            # Salvar original antes de editar (se primeira vez)
            if not abertura.saldo_inicial_original:
                abertura.saldo_inicial_original = abertura.saldo_abertura

            valor_anterior = abertura.saldo_abertura

            # Atualizar abertura
            abertura.saldo_abertura = novo_valor
            abertura.saldo_inicial_editado = True
            abertura.saldo_editado_em = timezone.now()
            abertura.saldo_editado_por = request.user
            abertura.save(
                update_fields=[
                    "saldo_abertura",
                    "saldo_inicial_editado",
                    "saldo_editado_em",
                    "saldo_editado_por",
                ]
            )

            # IMPORTANTE: Refresh abertura para garantir que saldo_movimentos use o novo valor
            abertura.refresh_from_db()

            # Atualizar saldo_atual do caixa para refletir a mudança
            caixa = abertura.caixa
            novo_saldo_atual = abertura.saldo_movimentos
            caixa.saldo_atual = novo_saldo_atual
            caixa.save(update_fields=["saldo_atual"])

            logger.info(
                f"Saldo inicial editado: {valor_anterior} -> {novo_valor}. "
                f"Saldo atual do caixa atualizado para: {novo_saldo_atual}"
            )

        # Retorna sucesso e força reload da página
        return HttpResponse(
            "<script>window.location.reload();</script>",
            status=200,
        )
