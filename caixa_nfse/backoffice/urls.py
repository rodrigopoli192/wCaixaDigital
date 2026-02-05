from django.urls import path

from . import views

app_name = "backoffice"

urlpatterns = [
    path("", views.PlatformDashboardView.as_view(), name="dashboard"),
    path("tenants/new/", views.TenantOnboardingView.as_view(), name="tenant_add"),
]
