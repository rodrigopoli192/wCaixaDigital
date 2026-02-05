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
]
