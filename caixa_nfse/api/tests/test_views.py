import pytest
from rest_framework import status
from rest_framework.test import APIClient

from caixa_nfse.tests.factories import (
    CaixaFactory,
    ClienteFactory,
    NotaFiscalServicoFactory,
    TenantFactory,
    UserFactory,
)


@pytest.mark.django_db
class TestCaixaViewSet:
    def setup_method(self):
        self.tenant = TenantFactory()
        self.user = UserFactory(tenant=self.tenant)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.url = "/api/v1/caixas/"

    def test_list_caixas_tenant_isolation(self):
        """Deve listar apenas caixas do tenant."""
        c1 = CaixaFactory(tenant=self.tenant)
        c2 = CaixaFactory(tenant=TenantFactory())  # Outro tenant

        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        ids = [i["id"] for i in response.data["results"]]
        assert str(c1.id) in ids
        assert str(c2.id) not in ids

    def test_list_no_tenant_user(self):
        """Usuário sem tenant não deve ver nada."""
        user_no_tenant = UserFactory(tenant=None)
        client = APIClient()
        client.force_authenticate(user=user_no_tenant)
        CaixaFactory(tenant=self.tenant)

        response = client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 0

    def test_create_caixa(self):
        data = {"identificador": "NEW01", "tipo": "FISICO", "status": "FECHADO", "ativo": True}
        response = self.client.post(self.url, data)
        assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
class TestClienteViewSet:
    def setup_method(self):
        self.tenant = TenantFactory()
        self.user = UserFactory(tenant=self.tenant)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.url = "/api/v1/clientes/"

    def test_list_clientes(self):
        c1 = ClienteFactory(tenant=self.tenant)
        c2 = ClienteFactory(tenant=TenantFactory())

        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        ids = [i["id"] for i in response.data["results"]]
        assert str(c1.id) in ids
        assert str(c2.id) not in ids

    def test_create_cliente(self):
        data = {
            "tipo_pessoa": "PF",
            "cpf_cnpj": "11122233344",
            "razao_social": "Cliente Novo",
            "nome_fantasia": "Novo",
            "ativo": True,
            "uf": "SP",
            "email": "new@test.com",
        }
        response = self.client.post(self.url, data)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["razao_social"] == "Cliente Novo"


@pytest.mark.django_db
class TestNotaFiscalViewSet:
    def setup_method(self):
        self.tenant = TenantFactory()
        self.user = UserFactory(tenant=self.tenant)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.url = "/api/v1/notas/"

    def test_list_notas(self):
        n1 = NotaFiscalServicoFactory(tenant=self.tenant)
        n2 = NotaFiscalServicoFactory(tenant=TenantFactory())
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        ids = [i["id"] for i in response.data["results"]]
        assert str(n1.id) in ids
        assert str(n2.id) not in ids

    def test_create_nota_simple(self):
        """Test basic create to cover perform_create."""
        from django.utils import timezone

        from caixa_nfse.nfse.models import ServicoMunicipal

        servico = ServicoMunicipal.objects.create(
            codigo_lc116="1.01",
            descricao="Análise e desenvolvimento de sistemas",
            municipio_ibge="3550308",
        )

        cliente = ClienteFactory(tenant=self.tenant)
        data = {
            "cliente": cliente.id,
            "numero_rps": 123,
            "serie_rps": "1",
            "servico": servico.id,
            "discriminacao": "Serviços de TI",
            "competencia": str(timezone.now().date()),
            "data_emissao": str(timezone.now().date()),
            "valor_servicos": "100.00",
            "aliquota_iss": "0.0500",
            "local_prestacao_ibge": "3550308",
        }
        response = self.client.post(self.url, data)
        assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
class TestAuth:
    def test_unauthenticated(self):
        client = APIClient()
        response = client.get("/api/v1/caixas/")
        assert response.status_code == status.HTTP_403_FORBIDDEN
