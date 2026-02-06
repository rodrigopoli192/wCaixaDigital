"""
API Views - DRF ViewSets.
"""

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from caixa_nfse.caixa.models import Caixa
from caixa_nfse.clientes.models import Cliente
from caixa_nfse.nfse.models import NotaFiscalServico

from .serializers import CaixaSerializer, ClienteSerializer, NotaFiscalSerializer


class TenantFilterMixin:
    """Filter queryset by user's tenant."""

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.tenant:
            return qs.filter(tenant=self.request.user.tenant)
        return qs.none()


class CaixaViewSet(TenantFilterMixin, viewsets.ModelViewSet):
    """API endpoint for Caixa."""

    queryset = Caixa.objects.all()
    serializer_class = CaixaSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["status", "tipo", "ativo"]
    search_fields = ["identificador"]

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.user.tenant)


class ClienteViewSet(TenantFilterMixin, viewsets.ModelViewSet):
    """API endpoint for Cliente."""

    queryset = Cliente.objects.all()
    serializer_class = ClienteSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["tipo_pessoa", "ativo", "uf"]
    search_fields = ["razao_social", "cpf_cnpj"]

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.user.tenant)


class NotaFiscalViewSet(TenantFilterMixin, viewsets.ModelViewSet):
    """API endpoint for NotaFiscalServico."""

    queryset = NotaFiscalServico.objects.all()
    serializer_class = NotaFiscalSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["status", "data_emissao"]
    search_fields = ["numero_rps", "numero_nfse"]

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.user.tenant)
