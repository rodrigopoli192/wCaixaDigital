"""
Core views.
"""

import socket
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm, SetPasswordForm
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import PasswordChangeView
from django.db import models
from django.db.models import Case, F, Q, Sum, Value, When
from django.db.models.functions import Coalesce
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, ListView, TemplateView, UpdateView

from .forms import ConexaoExternaForm, FormaPagamentoForm
from .models import ConexaoExterna, FormaPagamento

User = get_user_model()


class DashboardView(LoginRequiredMixin, TemplateView):
    """Main dashboard view - redirects based on user role."""

    def get(self, request, *args, **kwargs):
        # Redirect Superuser to Backoffice
        if request.user.is_superuser:
            return redirect("backoffice:dashboard")
        return super().get(request, *args, **kwargs)

    def get_template_names(self):
        """Return template based on user permissions."""
        user = self.request.user
        if user.pode_aprovar_fechamento:
            return ["core/dashboard_admin.html"]
        return ["core/dashboard_operador.html"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        if user.is_superuser or user.pode_aprovar_fechamento:
            context.update(self._get_admin_context(user))
        else:
            context.update(self._get_operador_context(user))

        return context

    def _get_admin_context(self, user):
        """Context for admin dashboard with KPIs and alerts."""
        from caixa_nfse.caixa.models import (
            AberturaCaixa,
            Caixa,
            FechamentoCaixa,
            MovimentoCaixa,
            MovimentoImportado,
            StatusRecebimento,
        )
        from caixa_nfse.clientes.models import Cliente
        from caixa_nfse.core.models import Notificacao
        from caixa_nfse.nfse.models import NotaFiscalServico

        tenant = user.tenant
        hoje = timezone.now().date()

        # Filter by tenant if not superuser
        if tenant:
            caixas = Caixa.objects.filter(tenant=tenant)
            nfses = NotaFiscalServico.objects.filter(tenant=tenant)
            clientes = Cliente.objects.filter(tenant=tenant)
            fechamentos = FechamentoCaixa.objects.filter(abertura__caixa__tenant=tenant)
            movimentos_hoje = MovimentoCaixa.objects.filter(
                abertura__caixa__tenant=tenant, data_hora__date=hoje
            )
        else:
            caixas = Caixa.objects.all()
            nfses = NotaFiscalServico.objects.all()
            clientes = Cliente.objects.all()
            fechamentos = FechamentoCaixa.objects.all()
            movimentos_hoje = MovimentoCaixa.objects.filter(data_hora__date=hoje)

        # KPIs
        caixas_abertos = caixas.filter(status="ABERTO").count()
        caixas_fechados = caixas.filter(status="FECHADO").count()

        vendas_hoje = (
            movimentos_hoje.filter(tipo="ENTRADA").aggregate(total=Sum("valor"))["total"] or 0
        )

        nfses_emitidas = nfses.filter(data_emissao=hoje).count()
        nfses_pendentes = nfses.filter(status="RASCUNHO").count()

        fechamentos_pendentes = fechamentos.filter(status="PENDENTE").count()

        # Alertas
        alertas = []
        if tenant and tenant.certificado_validade:
            dias_para_vencer = (tenant.certificado_validade - hoje).days
            if dias_para_vencer <= 30:
                alertas.append(
                    {
                        "tipo": "warning",
                        "titulo": "Certificado Digital",
                        "mensagem": f"Vence em {dias_para_vencer} dias",
                    }
                )

        if fechamentos_pendentes > 0:
            alertas.append(
                {
                    "tipo": "info",
                    "titulo": "Fechamentos Pendentes",
                    "mensagem": f"{fechamentos_pendentes} aguardando aprovação",
                }
            )

        # Caixas abertos há mais de 12 horas
        limite_horas = timezone.now() - timezone.timedelta(hours=12)
        caixas_antigos = AberturaCaixa.objects.filter(
            data_hora__lt=limite_horas, fechamento__isnull=True
        ).count()
        if caixas_antigos > 0:
            alertas.append(
                {
                    "tipo": "danger",
                    "titulo": "Atenção",
                    "mensagem": f"{caixas_antigos} caixa(s) aberto(s) há mais de 12h",
                }
            )

        # Últimas movimentações (todas)
        if tenant:
            ultimas_movimentacoes = (
                MovimentoCaixa.objects.filter(abertura__caixa__tenant=tenant)
                .select_related("abertura__caixa", "abertura__operador", "forma_pagamento")
                .order_by("-data_hora")[:5]
            )
            ultimas_nfses = nfses.select_related("cliente").order_by(
                "-data_emissao", "-created_at"
            )[:5]
        else:
            ultimas_movimentacoes = (
                MovimentoCaixa.objects.all()
                .select_related("abertura__caixa", "abertura__operador", "forma_pagamento")
                .order_by("-data_hora")[:5]
            )
            ultimas_nfses = nfses.select_related("cliente").order_by(
                "-data_emissao", "-created_at"
            )[:5]

        # Total de retenções (impostos do mês)
        inicio_mes = hoje.replace(day=1)
        retencoes_mes = (
            nfses.filter(data_emissao__gte=inicio_mes, status="AUTORIZADA").aggregate(
                total=Sum("valor_iss")
            )["total"]
            or 0
        )

        # Lista de todos os caixas com dados de abertura e valores
        caixas_lista = []
        for caixa in caixas.select_related("operador_atual").order_by("identificador"):
            # Buscar abertura ativa (não fechada)
            abertura_ativa = (
                AberturaCaixa.objects.filter(caixa=caixa, fechado=False)
                .select_related("operador")
                .first()
            )

            # Buscar último fechamento
            ultimo_fechamento = (
                FechamentoCaixa.objects.filter(abertura__caixa=caixa)
                .select_related("abertura")
                .order_by("-data_hora")
                .first()
            )

            # Calcular totais se houver abertura ativa
            total_entradas_caixa = Decimal("0.00")
            total_saidas_caixa = Decimal("0.00")
            if abertura_ativa:
                totais = abertura_ativa.movimentos.aggregate(
                    entradas=Sum("valor", filter=models.Q(tipo__in=["ENTRADA", "SUPRIMENTO"])),
                    saidas=Sum("valor", filter=models.Q(tipo__in=["SAIDA", "SANGRIA", "ESTORNO"])),
                )
                total_entradas_caixa = totais["entradas"] or Decimal("0.00")
                total_saidas_caixa = totais["saidas"] or Decimal("0.00")

            caixas_lista.append(
                {
                    "caixa": caixa,
                    "abertura_ativa": abertura_ativa,
                    "ultimo_fechamento": ultimo_fechamento,
                    "total_entradas": total_entradas_caixa,
                    "total_saidas": total_saidas_caixa,
                }
            )

        # Protocolos pendentes/parciais/vencidos (global do tenant)
        if tenant:
            importados_qs = MovimentoImportado.objects.filter(tenant=tenant)
        else:
            importados_qs = MovimentoImportado.objects.all()

        protocolos_pendentes = importados_qs.filter(
            status_recebimento__in=[
                StatusRecebimento.PENDENTE,
                StatusRecebimento.PARCIAL,
            ]
        ).count()
        protocolos_vencidos = importados_qs.filter(
            status_recebimento=StatusRecebimento.VENCIDO
        ).count()

        # Unread notifications
        if tenant:
            notificacoes_count = Notificacao.objects.filter(tenant=tenant, lida=False).count()
        else:
            notificacoes_count = 0

        if protocolos_vencidos > 0:
            alertas.append(
                {
                    "tipo": "danger",
                    "titulo": "Protocolos Vencidos",
                    "mensagem": f"{protocolos_vencidos} protocolo(s) com prazo de pagamento vencido",
                }
            )

        # Top pending protocols for mini-table
        ultimos_pendentes = (
            importados_qs.filter(
                status_recebimento__in=[
                    StatusRecebimento.PENDENTE,
                    StatusRecebimento.PARCIAL,
                    StatusRecebimento.VENCIDO,
                ]
            )
            .select_related("abertura__caixa")
            .prefetch_related("parcelas")
            .order_by("prazo_quitacao", "-created_at")[:5]
        )

        return {
            "page_title": "Dashboard",
            "is_admin": True,
            "caixas_abertos": caixas_abertos,
            "caixas_fechados": caixas_fechados,
            "vendas_hoje": vendas_hoje,
            "nfses_emitidas": nfses_emitidas,
            "nfses_pendentes": nfses_pendentes,
            "fechamentos_pendentes": fechamentos_pendentes,
            "total_clientes": clientes.count(),
            "alertas": alertas,
            "ultimas_movimentacoes": ultimas_movimentacoes,
            "ultimas_nfses": ultimas_nfses,
            "retencoes_mes": retencoes_mes,
            "caixas_lista": caixas_lista,
            "hoje": hoje,
            "protocolos_pendentes": protocolos_pendentes,
            "protocolos_vencidos": protocolos_vencidos,
            "notificacoes_count": notificacoes_count,
            "ultimos_pendentes": ultimos_pendentes,
        }

    def _get_operador_context(self, user):
        """Context for operator dashboard with current caixa focus."""
        from caixa_nfse.caixa.models import (
            AberturaCaixa,
            Caixa,
            MovimentoCaixa,
            MovimentoImportado,
            StatusRecebimento,
        )

        tenant = user.tenant
        caixa_atual = None
        abertura_atual = None
        ultimos_movimentos = []
        total_entradas = 0
        total_saidas = 0
        pendentes_count = 0
        parciais_count = 0
        importados_count = 0
        parciais_list = []
        importados_list = []

        if tenant:
            # Find operator's open caixa
            abertura_atual = (
                AberturaCaixa.objects.filter(
                    caixa__tenant=tenant, operador=user, fechamento__isnull=True
                )
                .select_related("caixa")
                .first()
            )

            if abertura_atual:
                caixa_atual = abertura_atual.caixa
                movimentos = MovimentoCaixa.objects.filter(abertura=abertura_atual)
                ultimos_movimentos = movimentos.order_by("-data_hora")[:5]

                # Use mov.valor (actual payment) with fallback to taxa_sum for legacy records
                taxa_sum = sum(
                    Coalesce(F(f), Value(Decimal("0.00"))) for f in MovimentoCaixa.TAXA_FIELDS
                )
                valor_real = Case(
                    When(valor__gt=Decimal("0.00"), then=F("valor")),
                    default=taxa_sum,
                    output_field=models.DecimalField(),
                )
                totais = movimentos.aggregate(
                    entradas=Sum(
                        valor_real,
                        filter=Q(tipo__in=["ENTRADA", "SUPRIMENTO"]),
                        output_field=models.DecimalField(),
                    ),
                    saidas=Sum(
                        valor_real,
                        filter=Q(tipo__in=["SAIDA", "SANGRIA", "ESTORNO"]),
                        output_field=models.DecimalField(),
                    ),
                )
                total_entradas = totais["entradas"] or 0
                total_saidas = totais["saidas"] or 0

                pendentes_qs = (
                    MovimentoImportado.objects.filter(
                        abertura=abertura_atual,
                        tenant=tenant,
                    )
                    .exclude(status_recebimento=StatusRecebimento.QUITADO)
                    .select_related("rotina", "conexao")
                )
                pendentes_count = pendentes_qs.count()
                parciais_list = list(
                    pendentes_qs.filter(
                        confirmado=True, status_recebimento=StatusRecebimento.PARCIAL
                    )
                )
                importados_list = list(pendentes_qs.filter(confirmado=False))
                parciais_count = len(parciais_list)
                importados_count = len(importados_list)

            # All active caixas (available and in use)
            todos_caixas = (
                Caixa.objects.filter(tenant=tenant, ativo=True)
                .select_related("operador_atual")
                .order_by("identificador")
            )

            # Histórico de aberturas do operador (últimas 5)
            historico_aberturas = (
                AberturaCaixa.objects.filter(operador=user)
                .select_related("caixa")
                .order_by("-data_hora")[:5]
            )
        else:
            todos_caixas = Caixa.objects.none()
            historico_aberturas = []

        # Saldo atual: usar caixa.saldo_atual (real) ou calcular com saldo_abertura
        if caixa_atual:
            saldo_atual = caixa_atual.saldo_atual
        elif abertura_atual:
            saldo_atual = (abertura_atual.saldo_abertura or 0) + total_entradas - total_saidas
        else:
            saldo_atual = 0

        return {
            "page_title": "Meu Caixa",
            "is_admin": False,
            "caixa_atual": caixa_atual,
            "abertura_atual": abertura_atual,
            "ultimos_movimentos": ultimos_movimentos,
            "total_entradas": total_entradas,
            "total_saidas": total_saidas,
            "saldo_atual": saldo_atual,
            "todos_caixas": todos_caixas if not abertura_atual else [],
            "historico_aberturas": historico_aberturas,
            "pendentes_count": pendentes_count,
            "parciais_count": parciais_count,
            "importados_count": importados_count,
            "parciais_list": parciais_list,
            "importados_list": importados_list,
            "hoje": timezone.now().date(),
        }


class MovimentosListView(LoginRequiredMixin, TemplateView):
    """Lista de movimentos paginada para HTMX."""

    template_name = "core/partials/movimentos_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from django.core.paginator import Paginator

        from caixa_nfse.caixa.models import AberturaCaixa, Caixa, MovimentoCaixa

        user = self.request.user
        tenant = user.tenant
        is_gerente = user.pode_aprovar_fechamento

        # Pegar parâmetros de filtro
        tipo = self.request.GET.get("tipo", "")
        caixa = self.request.GET.get("caixa", "")
        page = self.request.GET.get("page", 1)

        # Query base - depende se é gerente ou operador
        if is_gerente:
            # Gerente vê todos os movimentos do tenant
            if tenant:
                movimentos = MovimentoCaixa.objects.filter(
                    abertura__caixa__tenant=tenant
                ).select_related("abertura__caixa", "abertura__operador", "forma_pagamento")
            else:
                movimentos = MovimentoCaixa.objects.all().select_related(
                    "abertura__caixa", "abertura__operador", "forma_pagamento"
                )
        else:
            # Operador vê apenas movimentos da sua abertura ativa
            abertura_ativa = AberturaCaixa.objects.filter(operador=user, fechado=False).first()
            if abertura_ativa:
                movimentos = MovimentoCaixa.objects.filter(abertura=abertura_ativa).select_related(
                    "abertura__caixa", "abertura__operador", "forma_pagamento"
                )
            else:
                movimentos = MovimentoCaixa.objects.none()

        # Aplicar filtros
        if tipo:
            movimentos = movimentos.filter(tipo=tipo)
        if caixa and is_gerente:
            movimentos = movimentos.filter(abertura__caixa__pk=caixa)

        movimentos = movimentos.order_by("-data_hora").prefetch_related(
            "parcela_recebimento",
            "parcela_recebimento__movimento_importado__parcelas",
            "parcela_recebimento__movimento_importado__parcelas__forma_pagamento",
            "parcela_recebimento__movimento_importado__parcelas__recebido_por",
        )

        # Totais gerais (antes da paginação, sobre todo o queryset filtrado)
        from django.db.models import Sum

        totais_geral = movimentos.aggregate(
            total_emolumento=Sum("emolumento"),
            total_valor=Sum("valor"),
            **{f"total_{f}": Sum(f) for f in MovimentoCaixa.TAXA_FIELDS if f != "emolumento"},
        )
        total_emolumento = totais_geral.get("total_emolumento") or Decimal("0.00")
        total_taxas = sum(
            totais_geral.get(f"total_{f}") or Decimal("0.00")
            for f in MovimentoCaixa.TAXA_FIELDS
            if f != "emolumento"
        )
        total_geral = total_emolumento + total_taxas
        total_valor_pago = totais_geral.get("total_valor") or Decimal("0.00")

        # Paginação
        paginator = Paginator(movimentos, 10)
        page_obj = paginator.get_page(page)

        # Caixas disponíveis para filtro (apenas para gerentes)
        caixas = []
        if is_gerente:
            if tenant:
                caixas = Caixa.objects.filter(tenant=tenant, ativo=True)
            else:
                caixas = Caixa.objects.filter(ativo=True)

        context["movimentos"] = page_obj
        context["page_obj"] = page_obj
        context["caixas"] = caixas
        context["filtro_tipo"] = tipo
        context["filtro_caixa"] = caixa
        context["is_gerente"] = is_gerente
        context["total_emolumento"] = total_emolumento
        context["total_taxas"] = total_taxas
        context["total_geral"] = total_geral
        context["total_valor_pago"] = total_valor_pago

        # Para link 'Ver Todos' no partial
        if not is_gerente:
            ab = AberturaCaixa.objects.filter(operador=user, fechado=False).first()
            context["movimentos_abertura_pk"] = ab.pk if ab else None

        return context


class HealthCheckView(View):
    """Health check endpoint for container orchestration."""

    def get(self, request):
        return JsonResponse(
            {
                "status": "healthy",
                "version": "0.1.0",
            }
        )


class TenantAdminRequiredMixin(UserPassesTestMixin):
    """Ensure user is a tenant admin (can approve closing)."""

    def test_func(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        return user.tenant and user.pode_aprovar_fechamento


class SettingsView(LoginRequiredMixin, TenantAdminRequiredMixin, TemplateView):
    """
    Settings dashboard for Tenant Admins.
    """

    template_name = "core/settings.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Configurações da Loja"
        context["active_tab"] = self.request.GET.get("tab", "users")  # Dynamic tab
        return context


class SettingsParametrosView(LoginRequiredMixin, TenantAdminRequiredMixin, View):
    """GET/POST for tenant integration parameters (HTMX partial)."""

    def get(self, request):
        return render(
            request,
            "core/settings/parametros.html",
            {
                "tenant": request.user.tenant,
            },
        )

    def post(self, request):
        tenant = request.user.tenant
        tenant.chave_servico_andamento_ri = request.POST.get(
            "chave_servico_andamento_ri", ""
        ).strip()
        tenant.save(update_fields=["chave_servico_andamento_ri"])
        return render(
            request,
            "core/settings/parametros.html",
            {
                "tenant": tenant,
                "saved": True,
            },
        )


class SettingsNFSeView(LoginRequiredMixin, TenantAdminRequiredMixin, View):
    """GET/POST for NFS-e configuration (HTMX partial)."""

    def _get_form_and_config(self, request, data=None, files=None):
        from caixa_nfse.nfse.models import ConfiguracaoNFSe
        from caixa_nfse.nfse.views import NFSeConfigForm

        tenant = request.user.tenant
        config, _created = ConfiguracaoNFSe.objects.get_or_create(tenant=tenant)
        form = (
            NFSeConfigForm(data, files, instance=config, tenant=tenant)
            if data
            else NFSeConfigForm(instance=config, tenant=tenant)
        )
        return form, config

    def _cert_info(self, request):
        tenant = request.user.tenant
        return {
            "has_cert": bool(tenant.certificado_digital),
            "cert_validade": tenant.certificado_validade,
            "cert_valido": tenant.certificado_valido
            if hasattr(tenant, "certificado_valido")
            else False,
        }

    def _context(self, request, form, config, **extra):
        ctx = {"form": form, "cert_info": self._cert_info(request)}
        if config.webhook_token:
            base = request.build_absolute_uri("/nfse/webhook/")
            ctx["webhook_url"] = f"{base}?token={config.webhook_token}"
        ctx.update(extra)
        return ctx

    def get(self, request):
        form, config = self._get_form_and_config(request)
        return render(
            request,
            "core/partials/settings_nfse.html",
            self._context(request, form, config),
        )

    def post(self, request):
        form, config = self._get_form_and_config(request, request.POST, request.FILES)
        if form.is_valid():
            form.save()
            form, config = self._get_form_and_config(request)
            return render(
                request,
                "core/partials/settings_nfse.html",
                self._context(request, form, config, saved=True),
            )
        return render(
            request,
            "core/partials/settings_nfse.html",
            self._context(request, form, config),
        )


class TenantUserListView(LoginRequiredMixin, TenantAdminRequiredMixin, ListView):
    """
    List users for the current tenant.
    Designed for HTMX partial loading.
    """

    model = User
    template_name = "core/partials/settings_users_list.html"
    context_object_name = "users"

    def get_queryset(self):
        return User.objects.filter(tenant=self.request.user.tenant).order_by("first_name")


class TenantUserCreateView(LoginRequiredMixin, TenantAdminRequiredMixin, CreateView):
    """
    Create a new user linked to the current tenant.
    """

    model = User
    fields = [
        "email",
        "first_name",
        "last_name",
        "cpf",
        "telefone",
        "cargo",
        "pode_operar_caixa",
        "pode_emitir_nfse",
        "pode_cancelar_nfse",
        "pode_aprovar_fechamento",
        "pode_exportar_dados",
        "is_active",
    ]
    template_name = "core/partials/settings_user_form.html"

    def form_valid(self, form):
        user = form.save(commit=False)
        user.tenant = self.request.user.tenant
        user.username = user.email  # Ensure username matches email
        user.set_password("mudar123")  # Default initial password
        user.save()

        # Return the updated list
        return JsonResponse({"status": "success"}, status=200)

    def get_success_url(self):
        return reverse_lazy("core:settings_users_list")


class TenantUserUpdateView(LoginRequiredMixin, TenantAdminRequiredMixin, UpdateView):
    """
    Update an existing user.
    """

    model = User
    fields = [
        "email",
        "first_name",
        "last_name",
        "cpf",
        "telefone",
        "cargo",
        "pode_operar_caixa",
        "pode_emitir_nfse",
        "pode_cancelar_nfse",
        "pode_aprovar_fechamento",
        "pode_exportar_dados",
        "is_active",
    ]
    template_name = "core/partials/settings_user_form.html"

    def get_queryset(self):
        # Ensure we can only edit users from own tenant
        return User.objects.filter(tenant=self.request.user.tenant)

    def form_valid(self, form):
        self.object = form.save()
        return JsonResponse({"status": "success"}, status=200)


class TenantUserPasswordResetView(LoginRequiredMixin, TenantAdminRequiredMixin, UpdateView):
    """
    Allow Tenant Admin to reset password for a user.
    """

    model = User
    form_class = SetPasswordForm
    template_name = "core/partials/modal_admin_password_reset.html"

    def get_queryset(self):
        # Ensure we can only edit users from own tenant
        return User.objects.filter(tenant=self.request.user.tenant)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # SetPasswordForm expects 'user' as the first positional argument
        # UpdateView calls get_form_kwargs which returns 'instance': self.object
        # We need to remove 'instance' because SetPasswordForm is not a ModelForm
        kwargs["user"] = self.get_object()
        if "instance" in kwargs:
            del kwargs["instance"]
        return kwargs

    def form_valid(self, form):
        form.save()
        messages.success(
            self.request, f"Senha redefinida com sucesso para {form.user.get_full_name()}!"
        )
        # Return empty response to close modal
        response = HttpResponse("")
        response["HX-Trigger"] = "passwordResetSuccess"
        return response


# =============================================================================
# Formas de Pagamento Views
# =============================================================================


class FormaPagamentoListView(LoginRequiredMixin, TenantAdminRequiredMixin, ListView):
    """
    List payment methods for the current tenant.
    Designed for HTMX partial loading.
    """

    model = FormaPagamento
    template_name = "core/partials/settings_formas_pagamento_list.html"
    context_object_name = "formas_pagamento"

    def get_queryset(self):
        return FormaPagamento.objects.filter(tenant=self.request.user.tenant).order_by("nome")


class FormaPagamentoCreateView(LoginRequiredMixin, TenantAdminRequiredMixin, CreateView):
    """
    Create a new payment method linked to the current tenant.
    """

    model = FormaPagamento
    form_class = FormaPagamentoForm
    template_name = "core/partials/settings_forma_pagamento_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_edit"] = False
        context["form_title"] = "Nova Forma de Pagamento"
        return context

    def form_valid(self, form):
        forma = form.save(commit=False)
        forma.tenant = self.request.user.tenant
        forma.created_by = self.request.user
        forma.save()
        return JsonResponse({"status": "success"}, status=200)


class FormaPagamentoUpdateView(LoginRequiredMixin, TenantAdminRequiredMixin, UpdateView):
    """
    Update an existing payment method.
    """

    model = FormaPagamento
    form_class = FormaPagamentoForm
    template_name = "core/partials/settings_forma_pagamento_form.html"

    def get_queryset(self):
        return FormaPagamento.objects.filter(tenant=self.request.user.tenant)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_edit"] = True
        context["form_title"] = f"Editar {self.object.nome}"
        return context

    def form_valid(self, form):
        self.object = form.save()
        self.object.updated_by = self.request.user
        self.object.save(update_fields=["updated_by", "updated_at"])
        return JsonResponse({"status": "success"}, status=200)


class FormaPagamentoDeleteView(LoginRequiredMixin, TenantAdminRequiredMixin, View):
    """
    Delete a payment method (soft-delete by deactivating).
    """

    def post(self, request, pk):
        forma = FormaPagamento.objects.filter(pk=pk, tenant=request.user.tenant).first()
        if forma:
            forma.ativo = False
            forma.updated_by = request.user
            forma.save(update_fields=["ativo", "updated_by", "updated_at"])
            return JsonResponse({"status": "success"}, status=200)
        return JsonResponse({"status": "error", "message": "Não encontrado"}, status=404)


# =============================================================================
# Conexões Externas Views
# =============================================================================


class ConexaoExternaListView(LoginRequiredMixin, TenantAdminRequiredMixin, ListView):
    """
    List external connections for the current tenant.
    Designed for HTMX partial loading.
    """

    model = ConexaoExterna
    template_name = "core/partials/settings_conexoes_list.html"
    context_object_name = "conexoes"

    def get_queryset(self):
        return ConexaoExterna.objects.filter(tenant=self.request.user.tenant).order_by("sistema")


class ConexaoExternaCreateView(LoginRequiredMixin, TenantAdminRequiredMixin, CreateView):
    """
    Create a new external connection linked to the current tenant.
    """

    model = ConexaoExterna
    form_class = ConexaoExternaForm
    template_name = "core/settings_conexao_form.html"

    def get_success_url(self):
        return reverse_lazy("core:settings") + "?tab=conexoes"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_edit"] = False
        context["form_title"] = "Nova Conexão"
        return context

    def form_valid(self, form):
        conexao = form.save(commit=False)
        conexao.tenant = self.request.user.tenant
        conexao.created_by = self.request.user
        conexao.save()
        messages.success(self.request, "Conexão criada com sucesso!")
        return super().form_valid(form)


class ConexaoExternaUpdateView(LoginRequiredMixin, TenantAdminRequiredMixin, UpdateView):
    """
    Update an existing external connection.
    """

    model = ConexaoExterna
    form_class = ConexaoExternaForm
    template_name = "core/settings_conexao_form.html"

    def get_success_url(self):
        return reverse_lazy("core:settings") + "?tab=conexoes"

    def get_queryset(self):
        return ConexaoExterna.objects.filter(tenant=self.request.user.tenant)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_edit"] = True
        context["form_title"] = f"Editar {self.object.sistema.nome}"
        return context

    def form_valid(self, form):
        self.object = form.save()
        self.object.updated_by = self.request.user
        self.object.save(update_fields=["updated_by", "updated_at"])
        messages.success(self.request, "Conexão atualizada com sucesso!")
        return super().form_valid(form)


class ConexaoExternaDeleteView(LoginRequiredMixin, TenantAdminRequiredMixin, View):
    """
    Delete an external connection (soft-delete).
    """

    def post(self, request, pk):
        conexao = ConexaoExterna.objects.filter(pk=pk, tenant=request.user.tenant).first()
        if conexao:
            conexao.ativo = False
            conexao.updated_by = request.user
            conexao.save(update_fields=["ativo", "updated_by", "updated_at"])
            return JsonResponse({"status": "success"}, status=200)
        return JsonResponse({"status": "error", "message": "Não encontrado"}, status=404)


class RotinasPorSistemaView(LoginRequiredMixin, TenantAdminRequiredMixin, View):
    """
    Returns a partial list of Rutines for a specific System.
    """

    def get(self, request):
        sistema_id = request.GET.get("sistema")
        conexao_id = request.GET.get("conexao_id")
        rotinas_ids = []

        if conexao_id:
            try:
                conexao = ConexaoExterna.objects.get(pk=conexao_id, tenant=request.user.tenant)
                rotinas_ids = list(conexao.rotinas.values_list("pk", flat=True))
            except ConexaoExterna.DoesNotExist:
                pass

        if not sistema_id:
            return HttpResponse("")

        # Dynamic import to avoid circular dependency risks
        from caixa_nfse.backoffice.models import Rotina

        rotinas = Rotina.objects.filter(sistema_id=sistema_id, ativo=True)

        return render(
            request,
            "core/partials/rotinas_list.html",
            {"rotinas": rotinas, "selected_ids": rotinas_ids, "conexao_id": conexao_id},
        )


class RotinasJsonView(LoginRequiredMixin, View):
    """JSON API: returns rotinas for a conexao's sistema."""

    def get(self, request):
        conexao_id = request.GET.get("conexao_id")
        if not conexao_id:
            return JsonResponse({"rotinas": []})

        try:
            conexao = ConexaoExterna.objects.get(pk=conexao_id, tenant=request.user.tenant)
        except ConexaoExterna.DoesNotExist:
            return JsonResponse({"rotinas": []})

        from caixa_nfse.backoffice.models import Rotina

        rotinas = Rotina.objects.filter(sistema=conexao.sistema, ativo=True).values(
            "pk", "nome", "descricao"
        )

        return JsonResponse(
            {
                "rotinas": [
                    {"id": str(r["pk"]), "nome": r["nome"], "descricao": r["descricao"] or ""}
                    for r in rotinas
                ]
            }
        )


class RotinaExecutionView(LoginRequiredMixin, TenantAdminRequiredMixin, View):
    """
    Handles parsing and execution of SQL Routines with variables.
    """

    def get(self, request, pk):
        from caixa_nfse.backoffice.models import Rotina
        from caixa_nfse.core.services.sql_executor import SQLExecutor

        try:
            rotina = Rotina.objects.get(pk=pk, ativo=True)
            sql = f"{rotina.sql_content}\n{rotina.sql_content_extra or ''}"
            variables = SQLExecutor.extract_variables(sql)

            # Context for template
            context = {
                "rotina": rotina,
                "variables": variables,
                "conexao_id": request.GET.get("conexao_id"),
            }

            return render(request, "core/partials/modal_rotina_execution.html", context)
        except Rotina.DoesNotExist:
            return HttpResponse("Rotina não encontrada", status=404)

    def post(self, request, pk):
        from caixa_nfse.backoffice.models import Rotina
        from caixa_nfse.core.services.sql_executor import SQLExecutor

        try:
            rotina = Rotina.objects.get(pk=pk, ativo=True)
            conexao_id = request.POST.get("conexao_id")

            if not conexao_id:
                return HttpResponse("Conexão não especificada", status=400)

            conexao = ConexaoExterna.objects.get(pk=conexao_id, tenant=request.user.tenant)

            # Build variables dict from POST data
            sql_parts = [rotina.sql_content.strip()]
            if rotina.sql_content_extra:
                sql_parts.append(rotina.sql_content_extra.strip())
            sql = "\n".join(sql_parts).replace("\r", "")
            variables = SQLExecutor.extract_variables(sql)
            params = {var: request.POST.get(var) for var in variables}

            # Execute
            headers, rows, logs = SQLExecutor.execute_routine(conexao, sql, params)

            return render(
                request,
                "core/partials/rotina_results.html",
                {"headers": headers, "rows": rows, "logs": logs, "rotina": rotina},
            )

        except Rotina.DoesNotExist:
            return HttpResponse("Rotina não encontrada", status=404)
        except ConexaoExterna.DoesNotExist:
            return HttpResponse("Conexão não encontrada", status=404)
        except Exception as e:
            return HttpResponse(f"Erro na execução: {str(e)}", status=500)


class UserProfileView(LoginRequiredMixin, UpdateView):
    """View to update user profile via HTMX modal."""

    model = User
    fields = ["first_name", "last_name", "cpf"]
    template_name = "core/partials/modal_profile.html"

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        self.object = form.save()
        # Return empty response with trigger to update UI and close modal
        response = HttpResponse("")
        response["HX-Trigger"] = "profileUpdated"
        return response

    def form_invalid(self, form):
        # Return form with errors to be re-rendered in modal
        return super().form_invalid(form)


class UserPasswordChangeView(LoginRequiredMixin, PasswordChangeView):
    """View to change password via HTMX modal."""

    template_name = "core/partials/modal_password.html"
    form_class = PasswordChangeForm
    success_url = reverse_lazy("core:dashboard")  # Fallback

    def form_valid(self, form):
        form.save()
        # Updating the session so the user isn't logged out
        update_session_auth_hash(self.request, form.user)

        # Return empty response with trigger or success message
        response = HttpResponse("")
        # Add a toast message or trigger if you have a toast system
        messages.success(self.request, "Senha alterada com sucesso!")
        response["HX-Trigger"] = "passwordChanged"  # You can listen to this if needed
        return response


from django.views import View


class ConexaoExternaTestView(View):
    """
    Test connection parameters provided in the form.
    Checks TCP reachability and Authentication if driver is available.
    """

    def post(self, request, *args, **kwargs):
        data = request.POST
        sistema = data.get("sistema")
        tipo = data.get("tipo_conexao")
        host = data.get("host")
        port = data.get("porta")
        database = data.get("database")
        user = data.get("usuario")
        password = data.get("senha")

        logs = []

        def log(msg, type="info"):
            timestamp = timezone.now().strftime("%H:%M:%S")
            logs.append({"time": timestamp, "msg": msg, "type": type})

        log(f"Iniciando teste de conexão para {sistema}...", "info")
        log(f"Target: {host}:{port} ({tipo})", "info")

        if not all([host, port, user, password]):
            log("ERRO: Campos obrigatórios faltando.", "error")
            return JsonResponse(
                {"status": "error", "message": "Preencha todos os campos.", "logs": logs}
            )

        try:
            port = int(port)
        except ValueError:
            log(f"ERRO: Porta '{port}' inválida.", "error")
            return JsonResponse({"status": "error", "message": "Porta inválida.", "logs": logs})

        # 1. TCP Connectivity Check
        log(f"Tentando handshake TCP em {host}:{port}...", "info")
        try:
            start_time = timezone.now()
            sock = socket.create_connection((host, port), timeout=3)
            sock.close()
            duration = (timezone.now() - start_time).total_seconds() * 1000
            log(f"SUCESSO: Porta TCP acessível ({duration:.0f}ms).", "success")
        except OSError as e:
            log(f"FALHA TCP: {str(e)}", "error")
            log("Verifique Firewall, VPN ou se o serviço está ativo.", "warning")
            return JsonResponse(
                {"status": "error", "message": f"Falha de Conexão TCP: {str(e)}", "logs": logs}
            )

        # 2. Driver-Specific Checks
        details = "Porta acessível."

        # PostgreSQL
        if tipo == "POSTGRES":
            log("Iniciando autenticação PostgreSQL (Driver: psycopg)...", "info")
            try:
                import psycopg

                conn_str = f"host={host} port={port} dbname={database} user={user} password={password} connect_timeout=3"
                with psycopg.connect(conn_str) as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT version()")
                        version = cur.fetchone()[0]
                        log(f"Conectado! Versão: {version}", "success")
                details += " Autenticação OK."
                log("Teste PostgreSQL concluído com êxito.", "success")
            except ImportError:
                log(
                    "AVISO: Driver 'psycopg' não instalado. Teste de autenticação pulado.",
                    "warning",
                )
            except Exception as e:
                log(f"ERRO de Autenticação: {str(e)}", "error")
                return JsonResponse(
                    {
                        "status": "error",
                        "message": f"Porta OK, mas falha na autenticação: {str(e)}",
                        "logs": logs,
                    }
                )

        # Firebird
        elif tipo == "FIREBIRD":
            log("Iniciando autenticação Firebird (Driver: fdb)...", "info")
            try:
                import fdb

                conn = fdb.connect(
                    host=host,
                    port=port,
                    database=database,
                    user=user,
                    password=password,
                    charset=data.get("charset", "WIN1252"),
                )
                db_info = conn.db_info(fdb.isc_info_ods_version)
                conn.close()
                log(f"Conectado! ODS Version: {db_info}", "success")
                details += " Autenticação OK."
            except ImportError:
                log("AVISO: Driver 'fdb' não instalado. Teste de autenticação pulado.", "warning")
            except Exception as e:
                log(f"ERRO de Autenticação: {str(e)}", "error")
                return JsonResponse(
                    {
                        "status": "error",
                        "message": f"Porta OK, mas falha na autenticação: {str(e)}",
                        "logs": logs,
                    }
                )

        # SQL Server
        elif tipo == "MSSQL":
            log("Iniciando autenticação SQL Server...", "info")
            drivers_found = False
            try:
                import pymssql

                log("Tentando driver 'pymssql'...", "info")
                conn = pymssql.connect(
                    server=host,
                    port=port,
                    user=user,
                    password=password,
                    database=database,
                    timeout=3,
                )

                with conn.cursor() as cursor:
                    cursor.execute("SELECT @@VERSION")
                    row = cursor.fetchone()
                    if row:
                        ver_str = str(row[0]).split("\\n")[0]
                        log(f"Conectado! Versão: {ver_str}", "success")

                conn.close()
                details += " Autenticação OK."
                drivers_found = True
            except ImportError:
                log("Driver 'pymssql' não encontrado.", "warning")
            except Exception as e:
                log(f"ERRO pymssql: {str(e)}", "error")
                return JsonResponse(
                    {
                        "status": "error",
                        "message": f"Porta OK, mas falha na autenticação: {str(e)}",
                        "logs": logs,
                    }
                )

            if not drivers_found:
                log("Nenhum driver MSSQL (pymssql/pyodbc) disponível.", "warning")

        return JsonResponse(
            {"status": "success", "message": f"Conexão Bem-Sucedida! {details}", "logs": logs}
        )


class NotificacoesDropdownView(LoginRequiredMixin, TemplateView):
    """HTMX partial: dropdown with recent unread notifications."""

    template_name = "core/partials/notificacoes_dropdown.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from caixa_nfse.core.models import Notificacao

        qs = Notificacao.objects.filter(tenant=self.request.user.tenant)
        # Show user-specific OR broadcast (destinatario=null)
        qs = qs.filter(
            models.Q(destinatario=self.request.user) | models.Q(destinatario__isnull=True)
        )
        ctx["notificacoes"] = qs.filter(lida=False).order_by("-created_at")[:10]
        ctx["total_nao_lidas"] = qs.filter(lida=False).count()
        return ctx


class NotificacaoMarcarLidaView(LoginRequiredMixin, View):
    """Mark single notification as read."""

    def post(self, request, pk):
        from django.http import HttpResponse

        from caixa_nfse.core.models import Notificacao

        try:
            notif = Notificacao.objects.get(pk=pk, tenant=request.user.tenant)
            notif.marcar_lida()
        except Notificacao.DoesNotExist:
            pass
        return HttpResponse(status=204)


class NotificacoesMarcarTodasLidasView(LoginRequiredMixin, View):
    """Mark all notifications as read for the user's tenant."""

    def post(self, request):
        from django.http import HttpResponse

        from caixa_nfse.core.models import Notificacao

        Notificacao.objects.filter(
            tenant=request.user.tenant,
            lida=False,
        ).filter(models.Q(destinatario=request.user) | models.Q(destinatario__isnull=True)).update(
            lida=True, lida_em=timezone.now()
        )
        return HttpResponse(status=204)
