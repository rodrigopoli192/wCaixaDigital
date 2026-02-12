"""
NFS-e reports — Export CSV, dashboard data, API log viewer.
"""

import csv
import json
import logging
from datetime import timedelta

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth
from django.http import HttpResponse
from django.utils import timezone
from django.views import View
from django.views.generic import ListView, TemplateView

from .models import NotaFiscalServico, StatusNFSe
from .views import TenantMixin

logger = logging.getLogger(__name__)


# ── CSV Export ─────────────────────────────────────────────


class NFSeExportCSVView(LoginRequiredMixin, TenantMixin, UserPassesTestMixin, View):
    """Export NFS-e list as CSV with current filters."""

    def test_func(self):
        return self.request.user.pode_emitir_nfse

    def get(self, request):
        qs = (
            NotaFiscalServico.objects.filter(
                tenant=request.user.tenant,
            )
            .select_related("cliente", "servico")
            .order_by("-data_emissao")
        )

        # Apply same filters as NFSeListView
        params = request.GET
        if status := params.get("status"):
            qs = qs.filter(status=status)
        if data_inicio := params.get("data_inicio"):
            qs = qs.filter(data_emissao__gte=data_inicio)
        if data_fim := params.get("data_fim"):
            qs = qs.filter(data_emissao__lte=data_fim)
        if cliente := params.get("cliente"):
            from django.db import models

            qs = qs.filter(
                models.Q(cliente__razao_social__icontains=cliente)
                | models.Q(cliente__cpf_cnpj__icontains=cliente)
            )

        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="nfse_export.csv"'
        response.write("\ufeff")  # UTF-8 BOM for Excel

        writer = csv.writer(response, delimiter=";")
        writer.writerow(
            [
                "Nº RPS",
                "Nº NFS-e",
                "Status",
                "Data Emissão",
                "Cliente",
                "CPF/CNPJ",
                "Serviço",
                "Valor Total",
                "Alíquota ISS",
                "Valor ISS",
                "ISS Retido",
            ]
        )

        for nota in qs[:5000]:  # Limit
            writer.writerow(
                [
                    nota.numero_rps,
                    nota.numero_nfse or "",
                    nota.get_status_display(),
                    nota.data_emissao.strftime("%d/%m/%Y") if nota.data_emissao else "",
                    nota.cliente.razao_social if nota.cliente else "",
                    nota.cliente.cpf_cnpj if nota.cliente else "",
                    nota.servico.descricao if nota.servico else "",
                    f"{nota.valor_servicos:.2f}".replace(".", ","),
                    f"{nota.aliquota_iss:.2f}".replace(".", ",") if nota.aliquota_iss else "",
                    f"{nota.valor_iss:.2f}".replace(".", ",") if nota.valor_iss else "",
                    "Sim" if nota.iss_retido else "Não",
                ]
            )

        return response


# ── Dashboard ──────────────────────────────────────────────


class NFSeDashboardView(LoginRequiredMixin, TenantMixin, UserPassesTestMixin, TemplateView):
    """NFS-e analytics dashboard with charts data."""

    template_name = "nfse/nfse_dashboard.html"

    def test_func(self):
        return self.request.user.pode_emitir_nfse

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tenant = self.request.user.tenant
        qs = NotaFiscalServico.objects.filter(tenant=tenant)

        # Period filter (default: last 12 months)
        meses = int(self.request.GET.get("meses", 12))
        data_inicio = timezone.now().date() - timedelta(days=meses * 30)
        qs_period = qs.filter(data_emissao__gte=data_inicio)

        # Status breakdown
        ctx["status_breakdown"] = list(
            qs_period.values("status")
            .annotate(
                count=Count("id"),
                total=Sum("valor_servicos"),
            )
            .order_by("status")
        )

        # Monthly aggregation
        ctx["monthly_data"] = list(
            qs_period.filter(
                status=StatusNFSe.AUTORIZADA,
            )
            .annotate(
                mes=TruncMonth("data_emissao"),
            )
            .values("mes")
            .annotate(
                count=Count("id"),
                total=Sum("valor_servicos"),
                iss=Sum("valor_iss"),
            )
            .order_by("mes")
        )

        # Top 10 clients by revenue
        ctx["top_clients"] = list(
            qs_period.filter(
                status=StatusNFSe.AUTORIZADA,
                cliente__isnull=False,
            )
            .values(
                "cliente__razao_social",
            )
            .annotate(
                count=Count("id"),
                total=Sum("valor_servicos"),
            )
            .order_by("-total")[:10]
        )

        # Summary KPIs
        autorizadas = qs_period.filter(status=StatusNFSe.AUTORIZADA)
        ctx["kpis"] = {
            "total_notas": qs_period.count(),
            "autorizadas": autorizadas.count(),
            "valor_servicos": autorizadas.aggregate(s=Sum("valor_servicos"))["s"] or 0,
            "iss_total": autorizadas.aggregate(s=Sum("valor_iss"))["s"] or 0,
        }
        ctx["meses"] = meses

        # Serialize monthly_data for Chart.js
        from django.core.serializers.json import DjangoJSONEncoder

        ctx["monthly_data"] = json.dumps(ctx["monthly_data"], cls=DjangoJSONEncoder)

        return ctx


# ── API Log Viewer ─────────────────────────────────────────


class NFSeApiLogListView(LoginRequiredMixin, TenantMixin, UserPassesTestMixin, ListView):
    """View API interaction logs for debugging and auditing."""

    template_name = "nfse/nfse_api_log.html"
    context_object_name = "logs"
    paginate_by = 50

    def test_func(self):
        return self.request.user.pode_aprovar_fechamento  # Manager only

    def get_queryset(self):
        from .models_api_log import NfseApiLog

        qs = NfseApiLog.objects.filter(
            tenant=self.request.user.tenant,
        ).order_by("-created_at")

        params = self.request.GET
        if method := params.get("method"):
            qs = qs.filter(method=method.upper())
        if status := params.get("status"):
            qs = qs.filter(status_code=int(status))
        if url := params.get("url"):
            qs = qs.filter(url__icontains=url)

        return qs
