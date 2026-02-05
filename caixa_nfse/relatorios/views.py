"""
Relatorios views - Report views for managers.
"""

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Count, Q, Sum
from django.views.generic import TemplateView

from caixa_nfse.auditoria.models import RegistroAuditoria
from caixa_nfse.caixa.models import (
    AberturaCaixa,
    Caixa,
    FechamentoCaixa,
    MovimentoCaixa,
    StatusFechamento,
)
from caixa_nfse.core.models import FormaPagamento


class GerenteRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Mixin que requer que o usuário seja gerente."""

    def test_func(self):
        return self.request.user.pode_aprovar_fechamento


class RelatoriosIndexView(GerenteRequiredMixin, TemplateView):
    """Página inicial de relatórios."""

    template_name = "relatorios/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Relatórios"
        return context


class MovimentacoesReportView(GerenteRequiredMixin, TemplateView):
    """Relatório de movimentações por período."""

    template_name = "relatorios/financeiros/movimentacoes.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        tenant = user.tenant

        # Filtros
        data_inicio = self.request.GET.get("data_inicio", "")
        data_fim = self.request.GET.get("data_fim", "")
        tipo = self.request.GET.get("tipo", "")
        caixa_id = self.request.GET.get("caixa", "")
        forma_pgto_id = self.request.GET.get("forma_pagamento", "")

        # Query base
        movimentos = MovimentoCaixa.objects.filter(abertura__caixa__tenant=tenant).select_related(
            "abertura__caixa", "abertura__operador", "forma_pagamento"
        )

        # Aplicar filtros
        if data_inicio:
            movimentos = movimentos.filter(data_hora__date__gte=data_inicio)
        if data_fim:
            movimentos = movimentos.filter(data_hora__date__lte=data_fim)
        if tipo:
            movimentos = movimentos.filter(tipo=tipo)
        if caixa_id:
            movimentos = movimentos.filter(abertura__caixa__pk=caixa_id)
        if forma_pgto_id:
            movimentos = movimentos.filter(forma_pagamento__pk=forma_pgto_id)

        movimentos = movimentos.order_by("-data_hora")

        # Totais
        totais = movimentos.aggregate(
            total_entradas=Sum("valor", filter=Q(tipo__in=["ENTRADA", "SUPRIMENTO"])),
            total_saidas=Sum("valor", filter=Q(tipo__in=["SAIDA", "SANGRIA", "ESTORNO"])),
            count=Count("id"),
        )

        # Listas para filtros
        caixas = Caixa.objects.filter(tenant=tenant, ativo=True)
        formas_pagamento = FormaPagamento.objects.filter(tenant=tenant, ativo=True)

        context.update(
            {
                "page_title": "Movimentações por Período",
                "movimentos": movimentos[:100],  # Limitar para performance
                "total_entradas": totais["total_entradas"] or 0,
                "total_saidas": totais["total_saidas"] or 0,
                "total_registros": totais["count"] or 0,
                "caixas": caixas,
                "formas_pagamento": formas_pagamento,
                "filtro_data_inicio": data_inicio,
                "filtro_data_fim": data_fim,
                "filtro_tipo": tipo,
                "filtro_caixa": caixa_id,
                "filtro_forma_pagamento": forma_pgto_id,
            }
        )
        return context


class ResumoCaixaReportView(GerenteRequiredMixin, TemplateView):
    """Relatório de resumo por caixa."""

    template_name = "relatorios/financeiros/resumo_caixa.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        tenant = user.tenant

        # Filtros
        data_inicio = self.request.GET.get("data_inicio", "")
        data_fim = self.request.GET.get("data_fim", "")
        caixa_id = self.request.GET.get("caixa", "")

        # Query base - aberturas com fechamento
        aberturas = AberturaCaixa.objects.filter(caixa__tenant=tenant).select_related(
            "caixa", "operador", "fechamento"
        )

        # Aplicar filtros
        if data_inicio:
            aberturas = aberturas.filter(data_hora__date__gte=data_inicio)
        if data_fim:
            aberturas = aberturas.filter(data_hora__date__lte=data_fim)
        if caixa_id:
            aberturas = aberturas.filter(caixa__pk=caixa_id)

        aberturas = aberturas.order_by("-data_hora")

        # Enriquecer com totais
        resumos = []
        for abertura in aberturas[:50]:
            entradas = abertura.total_entradas
            saidas = abertura.total_saidas
            resumos.append(
                {
                    "abertura": abertura,
                    "saldo_inicial": abertura.saldo_abertura,
                    "entradas": entradas,
                    "saidas": saidas,
                    "saldo_final": abertura.saldo_abertura + entradas - saidas,
                    "fechamento": getattr(abertura, "fechamento", None),
                }
            )

        caixas = Caixa.objects.filter(tenant=tenant, ativo=True)

        context.update(
            {
                "page_title": "Resumo de Caixa",
                "resumos": resumos,
                "caixas": caixas,
                "filtro_data_inicio": data_inicio,
                "filtro_data_fim": data_fim,
                "filtro_caixa": caixa_id,
            }
        )
        return context


class FormasPagamentoReportView(GerenteRequiredMixin, TemplateView):
    """Relatório consolidado por forma de pagamento."""

    template_name = "relatorios/financeiros/formas_pagamento.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        tenant = user.tenant

        # Filtros
        data_inicio = self.request.GET.get("data_inicio", "")
        data_fim = self.request.GET.get("data_fim", "")

        # Query base
        movimentos = MovimentoCaixa.objects.filter(abertura__caixa__tenant=tenant)

        if data_inicio:
            movimentos = movimentos.filter(data_hora__date__gte=data_inicio)
        if data_fim:
            movimentos = movimentos.filter(data_hora__date__lte=data_fim)

        # Agrupar por forma de pagamento
        consolidado = (
            movimentos.values("forma_pagamento__nome")
            .annotate(
                total=Sum("valor"),
                quantidade=Count("id"),
            )
            .order_by("-total")
        )

        # Total geral
        total_geral = sum(item["total"] or 0 for item in consolidado)

        context.update(
            {
                "page_title": "Consolidado por Forma de Pagamento",
                "consolidado": consolidado,
                "total_geral": total_geral,
                "filtro_data_inicio": data_inicio,
                "filtro_data_fim": data_fim,
            }
        )
        return context


class PerformanceOperadorView(GerenteRequiredMixin, TemplateView):
    """Relatório de performance por operador."""

    template_name = "relatorios/operacionais/performance_operador.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        tenant = user.tenant

        # Filtros
        data_inicio = self.request.GET.get("data_inicio", "")
        data_fim = self.request.GET.get("data_fim", "")

        # Query base
        movimentos = MovimentoCaixa.objects.filter(abertura__caixa__tenant=tenant)

        if data_inicio:
            movimentos = movimentos.filter(data_hora__date__gte=data_inicio)
        if data_fim:
            movimentos = movimentos.filter(data_hora__date__lte=data_fim)

        # Agrupar por operador
        performance = (
            movimentos.values(
                "abertura__operador__first_name",
                "abertura__operador__email",
            )
            .annotate(
                total_movimentos=Count("id"),
                total_valor=Sum("valor"),
                total_entradas=Sum("valor", filter=Q(tipo__in=["ENTRADA", "SUPRIMENTO"])),
                total_saidas=Sum("valor", filter=Q(tipo__in=["SAIDA", "SANGRIA", "ESTORNO"])),
            )
            .order_by("-total_valor")
        )

        context.update(
            {
                "page_title": "Performance por Operador",
                "performance": performance,
                "filtro_data_inicio": data_inicio,
                "filtro_data_fim": data_fim,
            }
        )
        return context


class HistoricoAberturasView(GerenteRequiredMixin, TemplateView):
    """Relatório de histórico de aberturas/fechamentos."""

    template_name = "relatorios/operacionais/historico_aberturas.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        tenant = user.tenant

        # Filtros
        data_inicio = self.request.GET.get("data_inicio", "")
        data_fim = self.request.GET.get("data_fim", "")
        caixa_id = self.request.GET.get("caixa", "")

        # Query base
        aberturas = AberturaCaixa.objects.filter(caixa__tenant=tenant).select_related(
            "caixa", "operador", "fechamento"
        )

        if data_inicio:
            aberturas = aberturas.filter(data_hora__date__gte=data_inicio)
        if data_fim:
            aberturas = aberturas.filter(data_hora__date__lte=data_fim)
        if caixa_id:
            aberturas = aberturas.filter(caixa__pk=caixa_id)

        aberturas = aberturas.order_by("-data_hora")[:50]

        caixas = Caixa.objects.filter(tenant=tenant, ativo=True)

        context.update(
            {
                "page_title": "Histórico de Aberturas",
                "aberturas": aberturas,
                "caixas": caixas,
                "filtro_data_inicio": data_inicio,
                "filtro_data_fim": data_fim,
                "filtro_caixa": caixa_id,
            }
        )
        return context


class DiferencasCaixaView(GerenteRequiredMixin, TemplateView):
    """Relatório de diferenças de caixa."""

    template_name = "relatorios/operacionais/diferencas_caixa.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        tenant = user.tenant

        # Filtros
        data_inicio = self.request.GET.get("data_inicio", "")
        data_fim = self.request.GET.get("data_fim", "")
        apenas_diferencas = self.request.GET.get("apenas_diferencas", "")

        # Query base
        fechamentos = FechamentoCaixa.objects.filter(abertura__caixa__tenant=tenant).select_related(
            "abertura__caixa", "operador"
        )

        if data_inicio:
            fechamentos = fechamentos.filter(data_hora__date__gte=data_inicio)
        if data_fim:
            fechamentos = fechamentos.filter(data_hora__date__lte=data_fim)
        if apenas_diferencas:
            fechamentos = fechamentos.exclude(diferenca=0)

        fechamentos = fechamentos.order_by("-data_hora")[:50]

        context.update(
            {
                "page_title": "Diferenças de Caixa",
                "fechamentos": fechamentos,
                "filtro_data_inicio": data_inicio,
                "filtro_data_fim": data_fim,
                "filtro_apenas_diferencas": apenas_diferencas,
            }
        )
        return context


class LogAcoesView(GerenteRequiredMixin, TemplateView):
    """Relatório de log de ações de auditoria."""

    template_name = "relatorios/auditoria/log_acoes.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        tenant = user.tenant

        # Filtros
        data_inicio = self.request.GET.get("data_inicio", "")
        data_fim = self.request.GET.get("data_fim", "")
        acao = self.request.GET.get("acao", "")
        tabela = self.request.GET.get("tabela", "")

        # Query base
        registros = RegistroAuditoria.objects.filter(tenant=tenant).select_related("usuario")

        if data_inicio:
            registros = registros.filter(created_at__date__gte=data_inicio)
        if data_fim:
            registros = registros.filter(created_at__date__lte=data_fim)
        if acao:
            registros = registros.filter(acao=acao)
        if tabela:
            registros = registros.filter(tabela__icontains=tabela)

        registros = registros.order_by("-created_at")[:100]

        context.update(
            {
                "page_title": "Log de Ações",
                "registros": registros,
                "filtro_data_inicio": data_inicio,
                "filtro_data_fim": data_fim,
                "filtro_acao": acao,
                "filtro_tabela": tabela,
            }
        )
        return context


class FechamentosPendentesView(GerenteRequiredMixin, TemplateView):
    """Relatório de fechamentos pendentes de aprovação."""

    template_name = "relatorios/auditoria/fechamentos_pendentes.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        tenant = user.tenant

        # Query base - apenas pendentes
        fechamentos = (
            FechamentoCaixa.objects.filter(
                abertura__caixa__tenant=tenant,
                status=StatusFechamento.PENDENTE,
            )
            .select_related("abertura__caixa", "operador")
            .order_by("-data_hora")
        )

        context.update(
            {
                "page_title": "Fechamentos Pendentes",
                "fechamentos": fechamentos,
            }
        )
        return context
