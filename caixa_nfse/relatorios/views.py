"""
Relatorios views - Report views for managers.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
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

from .services import ExportService, format_currency


class GerenteRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Mixin que requer que o usuário seja gerente."""

    def test_func(self):
        return self.request.user.pode_aprovar_fechamento


class ExportMixin:
    """Mixin para suporte a exportação PDF/XLSX."""

    export_title = "Relatório"
    export_columns = []

    def get_export_data(self):
        """Override to return list of dicts for export."""
        return []

    def get_export_totals(self):
        """Override to return totals dict for export."""
        return {}

    def get_export_filters(self):
        """Return applied filters for export header."""
        filters = {}
        for key in ["data_inicio", "data_fim", "tipo", "caixa", "acao", "tabela"]:
            value = self.request.GET.get(key, "")
            if value:
                label = key.replace("_", " ").title()
                filters[label] = value
        return filters

    def handle_export(self, export_format):
        """Handle PDF/XLSX export request."""
        rows = self.get_export_data()
        totals = self.get_export_totals()
        filters = self.get_export_filters()
        tenant_name = getattr(self.request.user.tenant, "nome", "")

        if export_format == "pdf":
            return ExportService.to_pdf(
                title=self.export_title,
                columns=self.export_columns,
                rows=rows,
                totals=totals,
                filters=filters,
                tenant_name=tenant_name,
            )
        elif export_format == "xlsx":
            return ExportService.to_xlsx(
                title=self.export_title,
                columns=self.export_columns,
                rows=rows,
                totals=totals,
                filters=filters,
            )
        return None

    def get(self, request, *args, **kwargs):
        export_format = request.GET.get("export", "")
        if export_format in ["pdf", "xlsx"]:
            return self.handle_export(export_format)
        return super().get(request, *args, **kwargs)


class RelatoriosIndexView(GerenteRequiredMixin, TemplateView):
    """Página inicial de relatórios."""

    template_name = "relatorios/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Relatórios"
        return context


class MovimentacoesReportView(ExportMixin, GerenteRequiredMixin, TemplateView):
    """Relatório de movimentações por período."""

    template_name = "relatorios/financeiros/movimentacoes.html"
    export_title = "Movimentações por Período"
    export_columns = [
        {"key": "caixa", "label": "Caixa", "align": "left"},
        {"key": "operador", "label": "Operador", "align": "left"},
        {"key": "tipo", "label": "Tipo", "align": "left"},
        {"key": "forma_pagamento", "label": "Forma Pgto", "align": "left"},
        {"key": "descricao", "label": "Descrição", "align": "left"},
        {"key": "data_hora", "label": "Data/Hora", "align": "left"},
        {"key": "valor", "label": "Valor", "align": "right"},
    ]

    def get_queryset(self):
        tenant = self.request.user.tenant
        data_inicio = self.request.GET.get("data_inicio", "")
        data_fim = self.request.GET.get("data_fim", "")
        tipo = self.request.GET.get("tipo", "")
        caixa_id = self.request.GET.get("caixa", "")

        movimentos = MovimentoCaixa.objects.filter(abertura__caixa__tenant=tenant).select_related(
            "abertura__caixa", "abertura__operador", "forma_pagamento"
        )

        if data_inicio:
            movimentos = movimentos.filter(data_hora__date__gte=data_inicio)
        if data_fim:
            movimentos = movimentos.filter(data_hora__date__lte=data_fim)
        if tipo:
            movimentos = movimentos.filter(tipo=tipo)
        if caixa_id:
            movimentos = movimentos.filter(abertura__caixa__pk=caixa_id)

        return movimentos.order_by("-data_hora")

    def get_export_data(self):
        rows = []
        for mov in self.get_queryset()[:500]:
            rows.append(
                {
                    "caixa": mov.abertura.caixa.identificador,
                    "operador": mov.abertura.operador.first_name or mov.abertura.operador.email,
                    "tipo": mov.get_tipo_display(),
                    "forma_pagamento": mov.forma_pagamento.nome if mov.forma_pagamento else "-",
                    "descricao": mov.descricao or "-",
                    "data_hora": mov.data_hora.strftime("%d/%m/%Y %H:%M"),
                    "valor": format_currency(mov.valor),
                }
            )
        return rows

    def get_export_totals(self):
        qs = self.get_queryset()
        totais = qs.aggregate(
            total_entradas=Sum("valor", filter=Q(tipo__in=["ENTRADA", "SUPRIMENTO"])),
            total_saidas=Sum("valor", filter=Q(tipo__in=["SAIDA", "SANGRIA", "ESTORNO"])),
        )
        return {
            "valor": f"Entradas: {format_currency(totais['total_entradas'])} | Saídas: {format_currency(totais['total_saidas'])}"
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.user.tenant
        movimentos = self.get_queryset()

        totais = movimentos.aggregate(
            total_entradas=Sum("valor", filter=Q(tipo__in=["ENTRADA", "SUPRIMENTO"])),
            total_saidas=Sum("valor", filter=Q(tipo__in=["SAIDA", "SANGRIA", "ESTORNO"])),
            count=Count("id"),
        )

        caixas = Caixa.objects.filter(tenant=tenant, ativo=True)
        formas_pagamento = FormaPagamento.objects.filter(tenant=tenant, ativo=True)

        context.update(
            {
                "page_title": self.export_title,
                "movimentos": movimentos[:100],
                "total_entradas": totais["total_entradas"] or 0,
                "total_saidas": totais["total_saidas"] or 0,
                "total_registros": totais["count"] or 0,
                "caixas": caixas,
                "formas_pagamento": formas_pagamento,
                "filtro_data_inicio": self.request.GET.get("data_inicio", ""),
                "filtro_data_fim": self.request.GET.get("data_fim", ""),
                "filtro_tipo": self.request.GET.get("tipo", ""),
                "filtro_caixa": self.request.GET.get("caixa", ""),
            }
        )
        return context


class ResumoCaixaReportView(ExportMixin, GerenteRequiredMixin, TemplateView):
    """Relatório de resumo por caixa."""

    template_name = "relatorios/financeiros/resumo_caixa.html"
    export_title = "Resumo de Caixa"
    export_columns = [
        {"key": "caixa", "label": "Caixa", "align": "left"},
        {"key": "operador", "label": "Operador", "align": "left"},
        {"key": "abertura", "label": "Abertura", "align": "left"},
        {"key": "saldo_inicial", "label": "Saldo Inicial", "align": "right"},
        {"key": "entradas", "label": "Entradas", "align": "right"},
        {"key": "saidas", "label": "Saídas", "align": "right"},
        {"key": "saldo_final", "label": "Saldo Final", "align": "right"},
        {"key": "status", "label": "Status", "align": "center"},
    ]

    def get_resumos(self):
        tenant = self.request.user.tenant
        data_inicio = self.request.GET.get("data_inicio", "")
        data_fim = self.request.GET.get("data_fim", "")
        caixa_id = self.request.GET.get("caixa", "")

        aberturas = AberturaCaixa.objects.filter(caixa__tenant=tenant).select_related(
            "caixa", "operador", "fechamento"
        )

        if data_inicio:
            aberturas = aberturas.filter(data_hora__date__gte=data_inicio)
        if data_fim:
            aberturas = aberturas.filter(data_hora__date__lte=data_fim)
        if caixa_id:
            aberturas = aberturas.filter(caixa__pk=caixa_id)

        resumos = []
        total_entradas = Decimal("0")
        total_saidas = Decimal("0")
        total_saldo_final = Decimal("0")

        for abertura in aberturas.order_by("-data_hora")[:50]:
            entradas = abertura.total_entradas or Decimal("0")
            saidas = abertura.total_saidas or Decimal("0")
            saldo_final = abertura.saldo_abertura + entradas - saidas

            total_entradas += entradas
            total_saidas += saidas
            total_saldo_final += saldo_final

            resumos.append(
                {
                    "abertura": abertura,
                    "saldo_inicial": abertura.saldo_abertura,
                    "entradas": entradas,
                    "saidas": saidas,
                    "saldo_final": saldo_final,
                    "fechamento": getattr(abertura, "fechamento", None),
                }
            )

        return resumos, total_entradas, total_saidas, total_saldo_final

    def get_export_data(self):
        resumos, _, _, _ = self.get_resumos()
        rows = []
        for r in resumos:
            rows.append(
                {
                    "caixa": r["abertura"].caixa.identificador,
                    "operador": r["abertura"].operador.first_name or r["abertura"].operador.email,
                    "abertura": r["abertura"].data_hora.strftime("%d/%m/%Y %H:%M"),
                    "saldo_inicial": format_currency(r["saldo_inicial"]),
                    "entradas": format_currency(r["entradas"]),
                    "saidas": format_currency(r["saidas"]),
                    "saldo_final": format_currency(r["saldo_final"]),
                    "status": "Fechado" if r["fechamento"] else "Aberto",
                }
            )
        return rows

    def get_export_totals(self):
        _, total_entradas, total_saidas, total_saldo = self.get_resumos()
        return {
            "entradas": format_currency(total_entradas),
            "saidas": format_currency(total_saidas),
            "saldo_final": format_currency(total_saldo),
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.user.tenant
        resumos, total_entradas, total_saidas, total_saldo = self.get_resumos()
        caixas = Caixa.objects.filter(tenant=tenant, ativo=True)

        context.update(
            {
                "page_title": self.export_title,
                "resumos": resumos,
                "total_entradas": total_entradas,
                "total_saidas": total_saidas,
                "total_saldo_final": total_saldo,
                "caixas": caixas,
                "filtro_data_inicio": self.request.GET.get("data_inicio", ""),
                "filtro_data_fim": self.request.GET.get("data_fim", ""),
                "filtro_caixa": self.request.GET.get("caixa", ""),
            }
        )
        return context


class FormasPagamentoReportView(ExportMixin, GerenteRequiredMixin, TemplateView):
    """Relatório consolidado por forma de pagamento."""

    template_name = "relatorios/financeiros/formas_pagamento.html"
    export_title = "Consolidado por Forma de Pagamento"
    export_columns = [
        {"key": "forma_pagamento", "label": "Forma de Pagamento", "align": "left"},
        {"key": "quantidade", "label": "Quantidade", "align": "right"},
        {"key": "total", "label": "Total", "align": "right"},
        {"key": "percentual", "label": "% do Total", "align": "right"},
    ]

    def get_consolidado(self):
        tenant = self.request.user.tenant
        data_inicio = self.request.GET.get("data_inicio", "")
        data_fim = self.request.GET.get("data_fim", "")

        movimentos = MovimentoCaixa.objects.filter(abertura__caixa__tenant=tenant)

        if data_inicio:
            movimentos = movimentos.filter(data_hora__date__gte=data_inicio)
        if data_fim:
            movimentos = movimentos.filter(data_hora__date__lte=data_fim)

        consolidado = (
            movimentos.values("forma_pagamento__nome")
            .annotate(
                total=Sum("valor"),
                quantidade=Count("id"),
            )
            .order_by("-total")
        )

        total_geral = sum(item["total"] or 0 for item in consolidado)
        total_quantidade = sum(item["quantidade"] or 0 for item in consolidado)

        return list(consolidado), total_geral, total_quantidade

    def get_export_data(self):
        consolidado, total_geral, _ = self.get_consolidado()
        rows = []
        for item in consolidado:
            percentual = (item["total"] / total_geral * 100) if total_geral else 0
            rows.append(
                {
                    "forma_pagamento": item["forma_pagamento__nome"] or "Não informado",
                    "quantidade": item["quantidade"],
                    "total": format_currency(item["total"]),
                    "percentual": f"{percentual:.1f}%",
                }
            )
        return rows

    def get_export_totals(self):
        _, total_geral, total_quantidade = self.get_consolidado()
        return {
            "quantidade": total_quantidade,
            "total": format_currency(total_geral),
            "percentual": "100%",
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        consolidado, total_geral, total_quantidade = self.get_consolidado()

        context.update(
            {
                "page_title": self.export_title,
                "consolidado": consolidado,
                "total_geral": total_geral,
                "total_quantidade": total_quantidade,
                "filtro_data_inicio": self.request.GET.get("data_inicio", ""),
                "filtro_data_fim": self.request.GET.get("data_fim", ""),
            }
        )
        return context


class PerformanceOperadorView(ExportMixin, GerenteRequiredMixin, TemplateView):
    """Relatório de performance por operador."""

    template_name = "relatorios/operacionais/performance_operador.html"
    export_title = "Performance por Operador"
    export_columns = [
        {"key": "operador", "label": "Operador", "align": "left"},
        {"key": "email", "label": "E-mail", "align": "left"},
        {"key": "movimentos", "label": "Movimentos", "align": "right"},
        {"key": "entradas", "label": "Entradas", "align": "right"},
        {"key": "saidas", "label": "Saídas", "align": "right"},
        {"key": "total", "label": "Total", "align": "right"},
    ]

    def get_performance(self):
        tenant = self.request.user.tenant
        data_inicio = self.request.GET.get("data_inicio", "")
        data_fim = self.request.GET.get("data_fim", "")

        movimentos = MovimentoCaixa.objects.filter(abertura__caixa__tenant=tenant)

        if data_inicio:
            movimentos = movimentos.filter(data_hora__date__gte=data_inicio)
        if data_fim:
            movimentos = movimentos.filter(data_hora__date__lte=data_fim)

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

        return list(performance)

    def get_export_data(self):
        rows = []
        for item in self.get_performance():
            rows.append(
                {
                    "operador": item["abertura__operador__first_name"] or "Operador",
                    "email": item["abertura__operador__email"],
                    "movimentos": item["total_movimentos"],
                    "entradas": format_currency(item["total_entradas"]),
                    "saidas": format_currency(item["total_saidas"]),
                    "total": format_currency(item["total_valor"]),
                }
            )
        return rows

    def get_export_totals(self):
        perf = self.get_performance()
        total_mov = sum(p["total_movimentos"] or 0 for p in perf)
        total_ent = sum(p["total_entradas"] or 0 for p in perf)
        total_sai = sum(p["total_saidas"] or 0 for p in perf)
        total_val = sum(p["total_valor"] or 0 for p in perf)
        return {
            "movimentos": total_mov,
            "entradas": format_currency(total_ent),
            "saidas": format_currency(total_sai),
            "total": format_currency(total_val),
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        performance = self.get_performance()
        totals = self.get_export_totals()

        context.update(
            {
                "page_title": self.export_title,
                "performance": performance,
                "total_movimentos": totals["movimentos"],
                "total_entradas": totals["entradas"],
                "total_saidas": totals["saidas"],
                "total_valor": totals["total"],
                "filtro_data_inicio": self.request.GET.get("data_inicio", ""),
                "filtro_data_fim": self.request.GET.get("data_fim", ""),
            }
        )
        return context


class HistoricoAberturasView(ExportMixin, GerenteRequiredMixin, TemplateView):
    """Relatório de histórico de aberturas/fechamentos."""

    template_name = "relatorios/operacionais/historico_aberturas.html"
    export_title = "Histórico de Aberturas"
    export_columns = [
        {"key": "caixa", "label": "Caixa", "align": "left"},
        {"key": "operador", "label": "Operador", "align": "left"},
        {"key": "abertura", "label": "Abertura", "align": "left"},
        {"key": "fechamento", "label": "Fechamento", "align": "left"},
        {"key": "status", "label": "Status", "align": "center"},
    ]

    def get_aberturas(self):
        tenant = self.request.user.tenant
        data_inicio = self.request.GET.get("data_inicio", "")
        data_fim = self.request.GET.get("data_fim", "")
        caixa_id = self.request.GET.get("caixa", "")

        aberturas = AberturaCaixa.objects.filter(caixa__tenant=tenant).select_related(
            "caixa", "operador", "fechamento"
        )

        if data_inicio:
            aberturas = aberturas.filter(data_hora__date__gte=data_inicio)
        if data_fim:
            aberturas = aberturas.filter(data_hora__date__lte=data_fim)
        if caixa_id:
            aberturas = aberturas.filter(caixa__pk=caixa_id)

        return aberturas.order_by("-data_hora")[:50]

    def get_export_data(self):
        rows = []
        for ab in self.get_aberturas():
            fechamento = getattr(ab, "fechamento", None)
            rows.append(
                {
                    "caixa": ab.caixa.identificador,
                    "operador": ab.operador.first_name or ab.operador.email,
                    "abertura": ab.data_hora.strftime("%d/%m/%Y %H:%M"),
                    "fechamento": fechamento.data_hora.strftime("%d/%m/%Y %H:%M")
                    if fechamento
                    else "-",
                    "status": "Fechado" if ab.fechado else "Aberto",
                }
            )
        return rows

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.user.tenant
        caixas = Caixa.objects.filter(tenant=tenant, ativo=True)

        context.update(
            {
                "page_title": self.export_title,
                "aberturas": self.get_aberturas(),
                "caixas": caixas,
                "filtro_data_inicio": self.request.GET.get("data_inicio", ""),
                "filtro_data_fim": self.request.GET.get("data_fim", ""),
                "filtro_caixa": self.request.GET.get("caixa", ""),
            }
        )
        return context


class DiferencasCaixaView(ExportMixin, GerenteRequiredMixin, TemplateView):
    """Relatório de diferenças de caixa."""

    template_name = "relatorios/operacionais/diferencas_caixa.html"
    export_title = "Diferenças de Caixa"
    export_columns = [
        {"key": "caixa", "label": "Caixa", "align": "left"},
        {"key": "operador", "label": "Operador", "align": "left"},
        {"key": "fechamento", "label": "Fechamento", "align": "left"},
        {"key": "saldo_sistema", "label": "Saldo Sistema", "align": "right"},
        {"key": "saldo_informado", "label": "Saldo Informado", "align": "right"},
        {"key": "diferenca", "label": "Diferença", "align": "right"},
    ]

    def get_fechamentos(self):
        tenant = self.request.user.tenant
        data_inicio = self.request.GET.get("data_inicio", "")
        data_fim = self.request.GET.get("data_fim", "")
        apenas_diferencas = self.request.GET.get("apenas_diferencas", "")

        fechamentos = FechamentoCaixa.objects.filter(abertura__caixa__tenant=tenant).select_related(
            "abertura__caixa", "operador"
        )

        if data_inicio:
            fechamentos = fechamentos.filter(data_hora__date__gte=data_inicio)
        if data_fim:
            fechamentos = fechamentos.filter(data_hora__date__lte=data_fim)
        if apenas_diferencas:
            fechamentos = fechamentos.exclude(diferenca=0)

        return fechamentos.order_by("-data_hora")[:50]

    def get_export_data(self):
        rows = []
        for f in self.get_fechamentos():
            rows.append(
                {
                    "caixa": f.abertura.caixa.identificador,
                    "operador": f.operador.first_name or f.operador.email,
                    "fechamento": f.data_hora.strftime("%d/%m/%Y %H:%M"),
                    "saldo_sistema": format_currency(f.saldo_sistema),
                    "saldo_informado": format_currency(f.saldo_informado),
                    "diferenca": format_currency(f.diferenca),
                }
            )
        return rows

    def get_export_totals(self):
        fech = self.get_fechamentos()
        total_dif = sum(f.diferenca or 0 for f in fech)
        return {"diferenca": format_currency(total_dif)}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        fechamentos = self.get_fechamentos()
        total_diferenca = sum(f.diferenca or 0 for f in fechamentos)

        context.update(
            {
                "page_title": self.export_title,
                "fechamentos": fechamentos,
                "total_diferenca": total_diferenca,
                "filtro_data_inicio": self.request.GET.get("data_inicio", ""),
                "filtro_data_fim": self.request.GET.get("data_fim", ""),
                "filtro_apenas_diferencas": self.request.GET.get("apenas_diferencas", ""),
            }
        )
        return context


class LogAcoesView(ExportMixin, GerenteRequiredMixin, TemplateView):
    """Relatório de log de ações de auditoria."""

    template_name = "relatorios/auditoria/log_acoes.html"
    export_title = "Log de Ações"
    export_columns = [
        {"key": "data_hora", "label": "Data/Hora", "align": "left"},
        {"key": "usuario", "label": "Usuário", "align": "left"},
        {"key": "acao", "label": "Ação", "align": "left"},
        {"key": "tabela", "label": "Tabela", "align": "left"},
        {"key": "registro_id", "label": "Registro", "align": "left"},
        {"key": "ip", "label": "IP", "align": "left"},
    ]

    def get_registros(self):
        tenant = self.request.user.tenant
        data_inicio = self.request.GET.get("data_inicio", "")
        data_fim = self.request.GET.get("data_fim", "")
        acao = self.request.GET.get("acao", "")
        tabela = self.request.GET.get("tabela", "")

        registros = RegistroAuditoria.objects.filter(tenant=tenant).select_related("usuario")

        if data_inicio:
            registros = registros.filter(created_at__date__gte=data_inicio)
        if data_fim:
            registros = registros.filter(created_at__date__lte=data_fim)
        if acao:
            registros = registros.filter(acao=acao)
        if tabela:
            registros = registros.filter(tabela__icontains=tabela)

        return registros.order_by("-created_at")[:100]

    def get_export_data(self):
        rows = []
        for r in self.get_registros():
            rows.append(
                {
                    "data_hora": r.created_at.strftime("%d/%m/%Y %H:%M:%S"),
                    "usuario": r.usuario.first_name if r.usuario else "-",
                    "acao": r.get_acao_display() if hasattr(r, "get_acao_display") else r.acao,
                    "tabela": r.tabela,
                    "registro_id": str(r.registro_id)[:12],
                    "ip": r.ip_address or "-",
                }
            )
        return rows

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context.update(
            {
                "page_title": self.export_title,
                "registros": self.get_registros(),
                "total_registros": self.get_registros().count(),
                "filtro_data_inicio": self.request.GET.get("data_inicio", ""),
                "filtro_data_fim": self.request.GET.get("data_fim", ""),
                "filtro_acao": self.request.GET.get("acao", ""),
                "filtro_tabela": self.request.GET.get("tabela", ""),
            }
        )
        return context


class FechamentosPendentesView(GerenteRequiredMixin, TemplateView):
    """Relatório de fechamentos pendentes de aprovação."""

    template_name = "relatorios/auditoria/fechamentos_pendentes.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.user.tenant

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


class DashboardAnaliticoView(GerenteRequiredMixin, TemplateView):
    """Dashboard analítico com gráficos."""

    template_name = "relatorios/dashboard_analitico.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.user.tenant
        periodo = self.request.GET.get("periodo", "7")

        try:
            dias = int(periodo)
        except ValueError:
            dias = 7

        data_inicio = timezone.now() - timedelta(days=dias)

        # Movimentos do período
        movimentos = MovimentoCaixa.objects.filter(
            abertura__caixa__tenant=tenant,
            data_hora__gte=data_inicio,
        )

        # Movimentações por dia (para gráfico de linha)
        mov_por_dia = (
            movimentos.annotate(dia=TruncDate("data_hora"))
            .values("dia")
            .annotate(
                entradas=Sum("valor", filter=Q(tipo__in=["ENTRADA", "SUPRIMENTO"])),
                saidas=Sum("valor", filter=Q(tipo__in=["SAIDA", "SANGRIA", "ESTORNO"])),
                total=Sum("valor"),
            )
            .order_by("dia")
        )

        # Por forma de pagamento (para doughnut)
        por_forma = (
            movimentos.values("forma_pagamento__nome")
            .annotate(total=Sum("valor"))
            .order_by("-total")[:5]
        )

        # Top operadores (para bar horizontal)
        top_operadores = (
            movimentos.values("abertura__operador__first_name")
            .annotate(total=Sum("valor"))
            .order_by("-total")[:5]
        )

        # KPIs
        totais = movimentos.aggregate(
            total_entradas=Sum("valor", filter=Q(tipo__in=["ENTRADA", "SUPRIMENTO"])),
            total_saidas=Sum("valor", filter=Q(tipo__in=["SAIDA", "SANGRIA", "ESTORNO"])),
            total_movimentos=Count("id"),
        )

        total_entradas = totais["total_entradas"] or 0
        total_saidas = totais["total_saidas"] or 0
        total_movimentos = totais["total_movimentos"] or 1

        ticket_medio = (total_entradas + total_saidas) / total_movimentos if total_movimentos else 0
        movimentos_por_dia = total_movimentos / dias if dias else 0

        # Preparar dados para Chart.js
        chart_labels = [d["dia"].strftime("%d/%m") for d in mov_por_dia]
        chart_entradas = [float(d["entradas"] or 0) for d in mov_por_dia]
        chart_saidas = [float(d["saidas"] or 0) for d in mov_por_dia]

        forma_labels = [f["forma_pagamento__nome"] or "Outros" for f in por_forma]
        forma_values = [float(f["total"] or 0) for f in por_forma]

        operador_labels = [
            o["abertura__operador__first_name"] or "Operador" for o in top_operadores
        ]
        operador_values = [float(o["total"] or 0) for o in top_operadores]

        context.update(
            {
                "page_title": "Dashboard Analítico",
                "periodo": dias,
                # KPIs
                "total_entradas": total_entradas,
                "total_saidas": total_saidas,
                "ticket_medio": ticket_medio,
                "movimentos_por_dia": movimentos_por_dia,
                "total_movimentos": total_movimentos,
                # Chart data (JSON)
                "chart_labels": chart_labels,
                "chart_entradas": chart_entradas,
                "chart_saidas": chart_saidas,
                "forma_labels": forma_labels,
                "forma_values": forma_values,
                "operador_labels": operador_labels,
                "operador_values": operador_values,
            }
        )
        return context
