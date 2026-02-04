from django.urls import path

from . import views

app_name = "fiscal"

urlpatterns = [
    path("livro/", views.LivroFiscalListView.as_view(), name="livro"),
    path("relatorio-iss/", views.RelatorioISSView.as_view(), name="relatorio_iss"),
    path("exportar/", views.ExportarFiscalView.as_view(), name="exportar"),
]
