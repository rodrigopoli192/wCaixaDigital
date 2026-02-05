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
        "tenants/<uuid:tenant_pk>/users/<uuid:pk>/edit/",
        views.TenantUserUpdateView.as_view(),
        name="tenant_user_edit",
    ),
]
