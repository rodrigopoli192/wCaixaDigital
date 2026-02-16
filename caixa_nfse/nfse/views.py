"""
NFS-e views.
"""

import logging

from django import forms
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import models
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from .forms import NFSeForm
from .models import ConfiguracaoNFSe, NotaFiscalServico, StatusNFSe

logger = logging.getLogger(__name__)


class TenantMixin:
    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.tenant:
            return qs.filter(tenant=self.request.user.tenant)
        return qs.none()


class NFSeListView(LoginRequiredMixin, TenantMixin, UserPassesTestMixin, ListView):
    model = NotaFiscalServico
    template_name = "nfse/nfse_list.html"
    context_object_name = "notas"
    paginate_by = 25

    def test_func(self):
        return self.request.user.pode_emitir_nfse

    def get_queryset(self):
        qs = super().get_queryset().select_related("cliente", "servico")
        user = self.request.user

        # Operador vê só suas notas; gerente vê todas do tenant
        if not user.pode_aprovar_fechamento:
            qs = qs.filter(created_by=user)

        params = self.request.GET

        if numero := params.get("numero"):
            qs = qs.filter(
                models.Q(numero_rps__icontains=numero) | models.Q(numero_nfse__icontains=numero)
            )
        if cliente := params.get("cliente"):
            qs = qs.filter(
                models.Q(cliente__razao_social__icontains=cliente)
                | models.Q(cliente__cpf_cnpj__icontains=cliente)
            )
        if status := params.get("status"):
            qs = qs.filter(status=status)
        if data_inicio := params.get("data_inicio"):
            qs = qs.filter(data_emissao__gte=data_inicio)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        is_gerente = user.pode_aprovar_fechamento
        base_qs = super().get_queryset()
        if not is_gerente:
            base_qs = base_qs.filter(created_by=user)
        ctx["stats"] = {
            "total": base_qs.count(),
            "autorizadas": base_qs.filter(status=StatusNFSe.AUTORIZADA).count(),
            "rascunhos": base_qs.filter(status=StatusNFSe.RASCUNHO).count(),
            "canceladas": base_qs.filter(status=StatusNFSe.CANCELADA).count(),
            "rejeitadas": base_qs.filter(status=StatusNFSe.REJEITADA).count(),
            "enviando": base_qs.filter(status=StatusNFSe.ENVIANDO).count(),
        }
        ctx["is_gerente"] = is_gerente
        return ctx


class NFSeDetailView(LoginRequiredMixin, TenantMixin, UserPassesTestMixin, DetailView):
    model = NotaFiscalServico
    template_name = "nfse/nfse_detail.html"
    context_object_name = "nota"

    def test_func(self):
        return self.request.user.pode_emitir_nfse

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["eventos"] = self.object.eventos.order_by("-data_hora")
        return ctx


class NFSeCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = NotaFiscalServico
    form_class = NFSeForm
    template_name = "nfse/nfse_form.html"
    success_url = reverse_lazy("nfse:list")

    def test_func(self):
        return self.request.user.pode_emitir_nfse

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        try:
            cfg = ConfiguracaoNFSe.objects.get(tenant=self.request.user.tenant)
            ctx["ambiente"] = cfg.get_ambiente_display()
        except ConfiguracaoNFSe.DoesNotExist:
            pass
        return ctx

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
    form_class = NFSeForm
    template_name = "nfse/nfse_form.html"
    success_url = reverse_lazy("nfse:list")

    def test_func(self):
        return self.request.user.pode_emitir_nfse

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        try:
            cfg = ConfiguracaoNFSe.objects.get(tenant=self.request.user.tenant)
            ctx["ambiente"] = cfg.get_ambiente_display()
        except ConfiguracaoNFSe.DoesNotExist:
            pass
        return ctx

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


_INPUT_CSS = (
    "w-full bg-slate-50 dark:bg-background-dark border "
    "border-slate-200 dark:border-border-dark rounded-lg px-4 py-2 text-sm "
    "focus:ring-2 focus:ring-primary focus:border-primary transition-all outline-none"
)


class NFSeConfigForm(forms.ModelForm):
    certificado_digital = forms.FileField(
        label="Certificado A1 (.pfx)",
        required=False,
        widget=forms.ClearableFileInput(
            attrs={
                "class": _INPUT_CSS,
                "accept": ".pfx,.p12",
            }
        ),
    )
    certificado_senha = forms.CharField(
        label="Senha do certificado",
        required=False,
        widget=forms.PasswordInput(
            attrs={"class": _INPUT_CSS, "placeholder": "••••••"},
            render_value=True,
        ),
    )

    class Meta:
        model = ConfiguracaoNFSe
        fields = [
            "backend",
            "ambiente",
            "gerar_nfse_ao_confirmar",
            "api_token",
            "api_secret",
            "webhook_token",
        ]
        widgets = {
            "backend": forms.Select(attrs={"class": _INPUT_CSS, "x-model": "backend"}),
            "ambiente": forms.Select(attrs={"class": _INPUT_CSS}),
            "gerar_nfse_ao_confirmar": forms.CheckboxInput(
                attrs={"class": "w-5 h-5 text-primary rounded focus:ring-primary cursor-pointer"}
            ),
            "api_token": forms.TextInput(
                attrs={"class": _INPUT_CSS, "placeholder": "Token da API"}
            ),
            "api_secret": forms.PasswordInput(
                attrs={"class": _INPUT_CSS, "placeholder": "••••••"},
                render_value=True,
            ),
            "webhook_token": forms.TextInput(
                attrs={
                    "class": _INPUT_CSS,
                    "placeholder": "Gerado automaticamente",
                    "readonly": "readonly",
                }
            ),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        if tenant and tenant.certificado_senha:
            self.fields["certificado_senha"].initial = tenant.certificado_senha

    def save(self, commit=True):
        import secrets

        config = super().save(commit=False)

        # Auto-generate webhook_token for gateway backends
        if not config.webhook_token and config.backend not in ("mock", "portal_nacional"):
            config.webhook_token = secrets.token_hex(32)

        if commit:
            config.save()

        if self.tenant:
            cert_file = self.cleaned_data.get("certificado_digital")
            cert_senha = self.cleaned_data.get("certificado_senha")
            updated = False
            if cert_file:
                self.tenant.certificado_digital = cert_file.read()
                updated = True
            if cert_senha:
                self.tenant.certificado_senha = cert_senha
                updated = True
            if updated and commit:
                self.tenant.save(update_fields=["certificado_digital", "certificado_senha"])
        return config


class NFSeTestarConexaoView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Testa conexão com backend NFS-e (HTMX endpoint)."""

    def test_func(self):
        return self.request.user.pode_aprovar_fechamento

    def post(self, request):
        from .backends import get_backend

        try:
            config = ConfiguracaoNFSe.objects.get(tenant=request.user.tenant)
            backend = get_backend(request.user.tenant)
            # Call connectivity check if available
            if hasattr(backend, "testar_conexao"):
                result = backend.testar_conexao(request.user.tenant)
                if result.get("sucesso"):
                    ctx = {
                        "toast_type": "success",
                        "toast_title": "Conexão OK",
                        "toast_message": f"Backend {config.get_backend_display()} respondeu com sucesso.",
                    }
                else:
                    ctx = {
                        "toast_type": "error",
                        "toast_title": "Falha na Conexão",
                        "toast_message": result.get("mensagem", "Erro desconhecido"),
                    }
            else:
                ctx = {
                    "toast_type": "success",
                    "toast_title": "Backend Carregado",
                    "toast_message": f"Backend {config.get_backend_display()} configurado.",
                }
        except ConfiguracaoNFSe.DoesNotExist:
            ctx = {
                "toast_type": "error",
                "toast_title": "Sem Configuração",
                "toast_message": "Configure o backend primeiro.",
            }
        except Exception as e:
            logger.exception("Erro ao testar conexão NFS-e")
            ctx = {
                "toast_type": "error",
                "toast_title": "Erro",
                "toast_message": str(e),
            }

        html = render_to_string("nfse/_nfse_toast.html", ctx, request=request)
        return HttpResponse(html)


class NFSeDANFSeDownloadView(LoginRequiredMixin, TenantMixin, View):
    """Download DANFSe (PDF) — redirect ou proxy via backend."""

    def get(self, request, pk):
        nota = get_object_or_404(NotaFiscalServico, pk=pk, tenant=request.user.tenant)

        # 1. Redirect se URL pública disponível
        if nota.pdf_url:
            return redirect(nota.pdf_url)

        # 2. Tenta baixar via backend
        from .backends.registry import get_backend

        try:
            backend = get_backend(nota.tenant)
            pdf_bytes = backend.baixar_danfse(nota, nota.tenant)
            if pdf_bytes:
                filename = f"danfse_{nota.numero_nfse or nota.numero_rps}.pdf"
                response = HttpResponse(pdf_bytes, content_type="application/pdf")
                response["Content-Disposition"] = f'inline; filename="{filename}"'
                return response
        except Exception:
            logger.exception("Erro ao baixar DANFSe nota %s", pk)

        messages.error(request, "DANFSe não disponível para esta nota.")
        return redirect("nfse:detail", pk=pk)
