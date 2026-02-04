from django.urls import path

from . import views

app_name = "nfse"

urlpatterns = [
    path("", views.NFSeListView.as_view(), name="list"),
    path("nova/", views.NFSeCreateView.as_view(), name="create"),
    path("<uuid:pk>/", views.NFSeDetailView.as_view(), name="detail"),
    path("<uuid:pk>/editar/", views.NFSeUpdateView.as_view(), name="update"),
    path("<uuid:pk>/enviar/", views.NFSeEnviarView.as_view(), name="enviar"),
    path("<uuid:pk>/cancelar/", views.NFSeCancelarView.as_view(), name="cancelar"),
    path("<uuid:pk>/xml/", views.NFSeXMLView.as_view(), name="xml"),
]
