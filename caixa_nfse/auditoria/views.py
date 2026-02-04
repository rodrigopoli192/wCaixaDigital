"""
Auditoria views.
"""

import csv
from datetime import datetime

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import HttpResponse, JsonResponse
from django.views import View
from django.views.generic import DetailView, ListView

from .models import RegistroAuditoria


class AuditoriaListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """Lista de registros de auditoria."""

    model = RegistroAuditoria
    template_name = "auditoria/auditoria_list.html"
    context_object_name = "registros"
    paginate_by = 100
    permission_required = "auditoria.view_registroauditoria"

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.tenant:
            qs = qs.filter(tenant=self.request.user.tenant)

        # Filtros
        tabela = self.request.GET.get("tabela")
        acao = self.request.GET.get("acao")
        usuario = self.request.GET.get("usuario")
        data_inicio = self.request.GET.get("data_inicio")
        data_fim = self.request.GET.get("data_fim")

        if tabela:
            qs = qs.filter(tabela=tabela)
        if acao:
            qs = qs.filter(acao=acao)
        if usuario:
            qs = qs.filter(usuario_id=usuario)
        if data_inicio:
            qs = qs.filter(created_at__date__gte=data_inicio)
        if data_fim:
            qs = qs.filter(created_at__date__lte=data_fim)

        return qs.select_related("usuario", "tenant")


class AuditoriaDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """Detalhes de um registro de auditoria."""

    model = RegistroAuditoria
    template_name = "auditoria/auditoria_detail.html"
    permission_required = "auditoria.view_registroauditoria"

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.tenant:
            qs = qs.filter(tenant=self.request.user.tenant)
        return qs


class VerificarIntegridadeView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Verifica integridade da trilha de auditoria."""

    permission_required = "auditoria.view_audit_report"

    def get(self, request):
        tenant = request.user.tenant
        is_valid, broken_records = RegistroAuditoria.verificar_integridade(tenant)

        return JsonResponse(
            {
                "integridade_ok": is_valid,
                "registros_corrompidos": broken_records[:100],  # Limit response
                "total_corrompidos": len(broken_records),
            }
        )


class ExportarAuditoriaView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Exporta registros de auditoria para CSV."""

    permission_required = "auditoria.export_audit_log"

    def get(self, request):
        tenant = request.user.tenant

        # Create response
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="auditoria_{timestamp}.csv"'

        writer = csv.writer(response)
        writer.writerow(
            [
                "Data/Hora",
                "Usuário",
                "Tabela",
                "Registro ID",
                "Ação",
                "IP",
                "Campos Alterados",
                "Hash",
            ]
        )

        qs = RegistroAuditoria.objects.filter(tenant=tenant).select_related("usuario")

        # Apply filters
        data_inicio = request.GET.get("data_inicio")
        data_fim = request.GET.get("data_fim")

        if data_inicio:
            qs = qs.filter(created_at__date__gte=data_inicio)
        if data_fim:
            qs = qs.filter(created_at__date__lte=data_fim)

        for registro in qs.iterator():
            writer.writerow(
                [
                    registro.created_at.strftime("%d/%m/%Y %H:%M:%S"),
                    str(registro.usuario) if registro.usuario else "",
                    registro.tabela,
                    registro.registro_id,
                    registro.get_acao_display(),
                    registro.ip_address or "",
                    ", ".join(registro.campos_alterados or []),
                    registro.hash_registro,
                ]
            )

        # Register export in audit
        RegistroAuditoria.registrar(
            tabela="RegistroAuditoria",
            registro_id="EXPORT",
            acao="EXPORT",
            request=request,
        )

        return response
