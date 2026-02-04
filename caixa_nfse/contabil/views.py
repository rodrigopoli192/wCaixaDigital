import csv

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.views.generic import DetailView, ListView, View

from .models import LancamentoContabil, PlanoContas


class TenantMixin:
    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.tenant:
            return qs.filter(tenant=self.request.user.tenant)
        return qs.none()


class PlanoContasListView(LoginRequiredMixin, TenantMixin, ListView):
    model = PlanoContas
    template_name = "contabil/plano_contas.html"


class LancamentoListView(LoginRequiredMixin, TenantMixin, ListView):
    model = LancamentoContabil
    template_name = "contabil/lancamento_list.html"
    paginate_by = 50


class LancamentoDetailView(LoginRequiredMixin, TenantMixin, DetailView):
    model = LancamentoContabil
    template_name = "contabil/lancamento_detail.html"


class ExportarLancamentosView(LoginRequiredMixin, View):
    def get(self, request):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="lancamentos.csv"'

        writer = csv.writer(response)
        writer.writerow(["Data", "Competência", "Documento", "Histórico", "Conta", "D/C", "Valor"])

        lancamentos = LancamentoContabil.objects.filter(
            tenant=request.user.tenant
        ).prefetch_related("partidas__conta")

        for lanc in lancamentos:
            for partida in lanc.partidas.all():
                writer.writerow(
                    [
                        lanc.data_lancamento.strftime("%d/%m/%Y"),
                        lanc.data_competencia.strftime("%m/%Y"),
                        lanc.numero_documento,
                        lanc.historico[:100],
                        partida.conta.codigo,
                        partida.tipo,
                        f"{partida.valor:.2f}",
                    ]
                )

        return response
