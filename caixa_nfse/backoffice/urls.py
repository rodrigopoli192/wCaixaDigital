from django.urls import path

from . import views

app_name = "backoffice"

urlpatterns = [
    path("", views.PlatformDashboardView.as_view(), name="dashboard"),
    path("tenants/new/", views.TenantOnboardingView.as_view(), name="tenant_add"),
    path("tenants/<uuid:pk>/edit/", views.TenantUpdateView.as_view(), name="tenant_edit"),
    path("tenants/<uuid:pk>/delete/", views.TenantDeleteView.as_view(), name="tenant_delete"),
    # Tenant User Management
    path(
        "tenants/<uuid:tenant_pk>/users/add/",
        views.TenantUserCreateView.as_view(),
        name="tenant_user_add",
    ),
    path(
        "tenants/<uuid:tenant_pk>/users/<int:pk>/edit/",
        views.TenantUserUpdateView.as_view(),
        name="tenant_user_edit",
    ),
    # Sistemas
    path("sistemas/", views.SistemaListView.as_view(), name="sistema_list"),
    path("sistemas/new/", views.SistemaCreateView.as_view(), name="sistema_add"),
    path("sistemas/<int:pk>/edit/", views.SistemaUpdateView.as_view(), name="sistema_edit"),
    path(
        "sistemas/<int:pk>/delete/",
        views.SistemaDeleteView.as_view(),
        name="sistema_delete",
    ),
    # Rotinas
    path(
        "sistemas/<int:sistema_pk>/rotinas/new/",
        views.RotinaCreateView.as_view(),
        name="rotina_add",
    ),
    path("rotinas/<int:pk>/edit/", views.RotinaUpdateView.as_view(), name="rotina_edit"),
    path(
        "rotinas/<int:pk>/delete/",
        views.RotinaDeleteView.as_view(),
        name="rotina_delete",
    ),
    # Health Check
    path(
        "tenants/<uuid:tenant_pk>/health-check/",
        views.TenantHealthCheckView.as_view(),
        name="tenant_health_check",
    ),
]
