from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.views.generic import ListView, TemplateView, View

from .models import LivroFiscalServicos


class TenantMixin:
    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.tenant:
            return qs.filter(tenant=self.request.user.tenant)
        return qs.none()


class LivroFiscalListView(LoginRequiredMixin, TenantMixin, ListView):
    model = LivroFiscalServicos
    template_name = "fiscal/livro_servicos.html"


class RelatorioISSView(LoginRequiredMixin, TemplateView):
    template_name = "fiscal/relatorio_iss.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # TODO: Agregar dados de ISS
        return context


class ExportarFiscalView(LoginRequiredMixin, View):
    def get(self, request):
        # TODO: Implementar exportação fiscal
        response = HttpResponse("Exportação em desenvolvimento", content_type="text/plain")
        return response
