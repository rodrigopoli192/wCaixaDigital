from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("caixas", views.CaixaViewSet, basename="caixa")
router.register("clientes", views.ClienteViewSet, basename="cliente")
router.register("notas", views.NotaFiscalViewSet, basename="nota")

urlpatterns = [
    path("", include(router.urls)),
]
