from django.urls import path

from . import views

app_name = "contabil"

urlpatterns = [
    path("plano-contas/", views.PlanoContasListView.as_view(), name="plano_contas"),
    # Placeholder for Missing View referenced in template
    path("plano-contas/novo/", views.PlanoContasListView.as_view(), name="conta_create"),
    path("lancamentos/", views.LancamentoListView.as_view(), name="lancamentos"),
    path("lancamentos/<uuid:pk>/", views.LancamentoDetailView.as_view(), name="lancamento_detail"),
    path("exportar/", views.ExportarLancamentosView.as_view(), name="exportar_lancamentos"),
]
