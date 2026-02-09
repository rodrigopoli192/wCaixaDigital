"""
Core URL configuration.
"""

from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    # Dashboard
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("movimentos/", views.MovimentosListView.as_view(), name="movimentos_list"),
    # User Profile
    path("perfil/", views.UserProfileView.as_view(), name="user_profile"),
    path("perfil/senha/", views.UserPasswordChangeView.as_view(), name="user_change_password"),
    # Authentication
    path("login/", LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", LogoutView.as_view(next_page="core:login"), name="logout"),
    # Health check
    path("health/", views.HealthCheckView.as_view(), name="health"),
    # Settings
    path("settings/", views.SettingsView.as_view(), name="settings"),
    path("settings/users/", views.TenantUserListView.as_view(), name="settings_users_list"),
    path("settings/users/add/", views.TenantUserCreateView.as_view(), name="settings_user_add"),
    path(
        "settings/users/<pk>/edit/", views.TenantUserUpdateView.as_view(), name="settings_user_edit"
    ),
    path(
        "settings/users/<pk>/reset-password/",
        views.TenantUserPasswordResetView.as_view(),
        name="settings_user_reset_password",
    ),
    # Payment Methods
    path(
        "settings/formas-pagamento/",
        views.FormaPagamentoListView.as_view(),
        name="settings_formas_pagamento_list",
    ),
    path(
        "settings/formas-pagamento/add/",
        views.FormaPagamentoCreateView.as_view(),
        name="settings_forma_pagamento_add",
    ),
    path(
        "settings/formas-pagamento/<pk>/edit/",
        views.FormaPagamentoUpdateView.as_view(),
        name="settings_forma_pagamento_edit",
    ),
    path(
        "settings/formas-pagamento/<pk>/delete/",
        views.FormaPagamentoDeleteView.as_view(),
        name="settings_forma_pagamento_delete",
    ),
    # External Connections
    path(
        "settings/conexoes/",
        views.ConexaoExternaListView.as_view(),
        name="settings_conexoes_list",
    ),
    path(
        "settings/conexoes/add/",
        views.ConexaoExternaCreateView.as_view(),
        name="settings_conexao_add",
    ),
    path(
        "settings/conexoes/<pk>/edit/",
        views.ConexaoExternaUpdateView.as_view(),
        name="settings_conexao_edit",
    ),
    path(
        "settings/conexoes/<pk>/delete/",
        views.ConexaoExternaDeleteView.as_view(),
        name="settings_conexao_delete",
    ),
    path(
        "settings/conexoes/test/",
        views.ConexaoExternaTestView.as_view(),
        name="settings_conexao_test",
    ),
    path(
        "api/rotinas-por-sistema/",
        views.RotinasPorSistemaView.as_view(),
        name="api_rotinas_por_sistema",
    ),
    path(
        "api/rotinas-execucao/<int:pk>/",
        views.RotinaExecutionView.as_view(),
        name="api_rotinas_execucao",
    ),
    path(
        "api/rotinas-json/",
        views.RotinasJsonView.as_view(),
        name="api_rotinas_json",
    ),
]
