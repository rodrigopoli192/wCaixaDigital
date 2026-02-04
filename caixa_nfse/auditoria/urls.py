"""
Auditoria URLs.
"""

from django.urls import path

from . import views

app_name = "auditoria"

urlpatterns = [
    path("", views.AuditoriaListView.as_view(), name="list"),
    path("<uuid:pk>/", views.AuditoriaDetailView.as_view(), name="detail"),
    path("verificar-integridade/", views.VerificarIntegridadeView.as_view(), name="verificar"),
    path("exportar/", views.ExportarAuditoriaView.as_view(), name="exportar"),
]
