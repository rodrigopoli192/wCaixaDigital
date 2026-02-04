from django.urls import path

from . import views

app_name = "clientes"

urlpatterns = [
    path("", views.ClienteListView.as_view(), name="list"),
    path("novo/", views.ClienteCreateView.as_view(), name="create"),
    path("<uuid:pk>/", views.ClienteDetailView.as_view(), name="detail"),
    path("<uuid:pk>/editar/", views.ClienteUpdateView.as_view(), name="update"),
]
