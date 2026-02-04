"""
NFS-e views - Placeholder implementation.
"""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from .models import NotaFiscalServico, StatusNFSe


class TenantMixin:
    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.tenant:
            return qs.filter(tenant=self.request.user.tenant)
        return qs.none()


class NFSeListView(LoginRequiredMixin, TenantMixin, ListView):
    model = NotaFiscalServico
    template_name = "nfse/nfse_list.html"
    context_object_name = "notas"
    paginate_by = 25

    def get_queryset(self):
        return super().get_queryset().select_related("cliente", "servico")


class NFSeDetailView(LoginRequiredMixin, TenantMixin, DetailView):
    model = NotaFiscalServico
    template_name = "nfse/nfse_detail.html"


class NFSeCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = NotaFiscalServico
    fields = [
        "cliente",
        "servico",
        "discriminacao",
        "competencia",
        "valor_servicos",
        "valor_deducoes",
        "valor_pis",
        "valor_cofins",
        "valor_inss",
        "valor_ir",
        "valor_csll",
        "aliquota_iss",
        "iss_retido",
        "local_prestacao_ibge",
    ]
    template_name = "nfse/nfse_form.html"
    success_url = reverse_lazy("nfse:list")

    def test_func(self):
        return self.request.user.pode_emitir_nfse

    def form_valid(self, form):
        tenant = self.request.user.tenant
        form.instance.tenant = tenant
        form.instance.numero_rps = tenant.proximo_numero_rps()
        form.instance.serie_rps = tenant.nfse_serie_padrao
        form.instance.created_by = self.request.user
        messages.success(self.request, "RPS gerado com sucesso!")
        return super().form_valid(form)


class NFSeUpdateView(LoginRequiredMixin, TenantMixin, UserPassesTestMixin, UpdateView):
    model = NotaFiscalServico
    fields = [
        "cliente",
        "servico",
        "discriminacao",
        "competencia",
        "valor_servicos",
        "valor_deducoes",
        "valor_pis",
        "valor_cofins",
        "valor_inss",
        "valor_ir",
        "valor_csll",
        "aliquota_iss",
        "iss_retido",
        "local_prestacao_ibge",
    ]
    template_name = "nfse/nfse_form.html"
    success_url = reverse_lazy("nfse:list")

    def test_func(self):
        return self.request.user.pode_emitir_nfse

    def get_queryset(self):
        return super().get_queryset().filter(status=StatusNFSe.RASCUNHO)


class NFSeEnviarView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Enviar RPS para autorização."""

    def test_func(self):
        return self.request.user.pode_emitir_nfse

    def post(self, request, pk):
        from .tasks import enviar_nfse

        nota = NotaFiscalServico.objects.get(pk=pk, tenant=request.user.tenant)

        if nota.status != StatusNFSe.RASCUNHO:
            messages.error(request, "Nota não está em rascunho.")
            return redirect("nfse:detail", pk=pk)

        # Envia tarefa assíncrona
        enviar_nfse.delay(str(nota.pk))

        nota.status = StatusNFSe.ENVIANDO
        nota.save(update_fields=["status"])

        messages.info(request, "Nota enviada para processamento.")
        return redirect("nfse:detail", pk=pk)


class NFSeCancelarView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Cancelar NFS-e."""

    def test_func(self):
        return self.request.user.pode_cancelar_nfse

    def post(self, request, pk):
        nota = NotaFiscalServico.objects.get(pk=pk, tenant=request.user.tenant)

        if not nota.pode_cancelar:
            messages.error(request, "Nota não pode ser cancelada.")
            return redirect("nfse:detail", pk=pk)

        motivo = request.POST.get("motivo", "")
        if not motivo:
            messages.error(request, "Motivo do cancelamento é obrigatório.")
            return redirect("nfse:detail", pk=pk)

        # TODO: Integrar com WebService
        messages.warning(request, "Funcionalidade em desenvolvimento.")
        return redirect("nfse:detail", pk=pk)


class NFSeXMLView(LoginRequiredMixin, TenantMixin, DetailView):
    """Download XML da NFS-e."""

    model = NotaFiscalServico

    def get(self, request, pk):
        nota = self.get_object()

        xml = nota.xml_nfse or nota.xml_rps
        if not xml:
            messages.error(request, "XML não disponível.")
            return redirect("nfse:detail", pk=pk)

        response = HttpResponse(xml, content_type="application/xml")
        response["Content-Disposition"] = f'attachment; filename="nfse_{nota.numero_rps}.xml"'
        return response
