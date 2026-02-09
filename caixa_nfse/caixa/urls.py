"""
Caixa URL configuration.
"""

from django.urls import path

from . import views

app_name = "caixa"

urlpatterns = [
    # Lista de caixas
    path("", views.CaixaListView.as_view(), name="list"),
    path("criar/", views.CaixaCreateView.as_view(), name="criar"),
    path("<uuid:pk>/", views.CaixaDetailView.as_view(), name="detail"),
    path("<uuid:pk>/editar/", views.CaixaUpdateView.as_view(), name="editar"),
    # Operações de caixa
    path("<uuid:pk>/abrir/", views.AbrirCaixaView.as_view(), name="abrir"),
    path("<uuid:pk>/fechar/", views.FecharCaixaView.as_view(), name="fechar"),
    # Movimentos
    path("abertura/<uuid:pk>/movimento/", views.NovoMovimentoView.as_view(), name="novo_movimento"),
    path(
        "abertura/<uuid:pk>/movimentos/",
        views.ListaMovimentosView.as_view(),
        name="lista_movimentos",
    ),
    # Importação de movimentos
    path(
        "abertura/<uuid:pk>/importar/",
        views.ImportarMovimentosView.as_view(),
        name="importar_movimentos",
    ),
    path(
        "abertura/<uuid:pk>/importados/",
        views.ListaImportadosView.as_view(),
        name="lista_importados",
    ),
    path(
        "abertura/<uuid:pk>/importados/confirmar/",
        views.ConfirmarImportadosView.as_view(),
        name="confirmar_importados",
    ),
    path(
        "abertura/<uuid:pk>/importados/excluir/",
        views.ExcluirImportadosView.as_view(),
        name="excluir_importados",
    ),
    # Fechamentos pendentes de aprovação
    path(
        "fechamentos/pendentes/",
        views.FechamentosPendentesView.as_view(),
        name="fechamentos_pendentes",
    ),
    path(
        "fechamento/<uuid:pk>/aprovar/",
        views.AprovarFechamentoView.as_view(),
        name="aprovar_fechamento",
    ),
]
