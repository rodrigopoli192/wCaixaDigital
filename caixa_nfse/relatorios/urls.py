"""
Relatorios URL configuration.
"""

from django.urls import path

from . import views

app_name = "relatorios"

urlpatterns = [
    # Dashboard de relatórios
    path("", views.RelatoriosIndexView.as_view(), name="index"),
    # Financeiros
    path("movimentacoes/", views.MovimentacoesReportView.as_view(), name="movimentacoes"),
    path("resumo-caixa/", views.ResumoCaixaReportView.as_view(), name="resumo_caixa"),
    path("formas-pagamento/", views.FormasPagamentoReportView.as_view(), name="formas_pagamento"),
    # Operacionais
    path(
        "performance-operador/",
        views.PerformanceOperadorView.as_view(),
        name="performance_operador",
    ),
    path(
        "historico-aberturas/", views.HistoricoAberturasView.as_view(), name="historico_aberturas"
    ),
    path("diferencas-caixa/", views.DiferencasCaixaView.as_view(), name="diferencas_caixa"),
    # Auditoria
    path("log-acoes/", views.LogAcoesView.as_view(), name="log_acoes"),
    path(
        "fechamentos-pendentes/",
        views.FechamentosPendentesView.as_view(),
        name="fechamentos_pendentes",
    ),
]
