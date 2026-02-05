"""
Core views.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import models
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, ListView, TemplateView, UpdateView

from .forms import FormaPagamentoForm
from .models import FormaPagamento

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
        from caixa_nfse.caixa.models import AberturaCaixa, Caixa, FechamentoCaixa, MovimentoCaixa
        from caixa_nfse.clientes.models import Cliente
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

        fechamentos_pendentes = fechamentos.filter(status="PENDENTE_APROVACAO").count()

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

        return {
            "page_title": "Dashboard de Compliance",
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
        }

    def _get_operador_context(self, user):
        """Context for operator dashboard with current caixa focus."""
        from caixa_nfse.caixa.models import AberturaCaixa, Caixa, MovimentoCaixa

        tenant = user.tenant
        caixa_atual = None
        abertura_atual = None
        ultimos_movimentos = []
        total_entradas = 0
        total_saidas = 0

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

                totais = movimentos.aggregate(
                    entradas=Sum("valor", filter=Q(tipo="ENTRADA")),
                    saidas=Sum("valor", filter=Q(tipo="SAIDA")),
                )
                total_entradas = totais["entradas"] or 0
                total_saidas = totais["saidas"] or 0

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

        return {
            "page_title": "Meu Caixa",
            "is_admin": False,
            "caixa_atual": caixa_atual,
            "abertura_atual": abertura_atual,
            "ultimos_movimentos": ultimos_movimentos,
            "total_entradas": total_entradas,
            "total_saidas": total_saidas,
            "saldo_atual": total_entradas - total_saidas,
            "todos_caixas": todos_caixas if not abertura_atual else [],
            "historico_aberturas": historico_aberturas,
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

        movimentos = movimentos.order_by("-data_hora")

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
        return user.is_authenticated and user.tenant and user.pode_aprovar_fechamento


class SettingsView(LoginRequiredMixin, TenantAdminRequiredMixin, TemplateView):
    """
    Settings dashboard for Tenant Admins.
    """

    template_name = "core/settings.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Configurações da Loja"
        context["active_tab"] = "users"  # Default tab
        return context


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
