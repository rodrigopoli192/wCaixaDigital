import pytest
from django.urls import reverse

from caixa_nfse.fiscal.models import LivroFiscalServicos
from caixa_nfse.tests.factories import TenantFactory, UserFactory


@pytest.mark.django_db
class TestFiscalViews:
    def setup_method(self):
        self.tenant = TenantFactory()
        self.user = UserFactory(tenant=self.tenant)
        self.livro = LivroFiscalServicos.objects.create(
            tenant=self.tenant,
            competencia="2023-01-01",
            municipio_ibge="3550308",
            valor_servicos="1000.00",
            valor_iss="50.00",
            valor_iss_retido="0.00",
        )

        from django.test import Client

        self.client = Client()
        self.client.force_login(self.user)

    def test_livro_list_access(self):
        url = reverse("fiscal:livro")
        response = self.client.get(url)
        assert response.status_code == 200
        assert self.livro in response.context["object_list"]

    def test_relatorio_iss_access(self):
        url = reverse("fiscal:relatorio_iss")
        response = self.client.get(url)
        assert response.status_code == 200

    def test_export_fiscal_access(self):
        url = reverse("fiscal:exportar")
        response = self.client.get(url)
        assert response.status_code == 200
        assert "Exportação em desenvolvimento" in response.content.decode("utf-8")

    def test_livro_list_tenant_isolation(self):
        other_tenant = TenantFactory()
        other_livro = LivroFiscalServicos.objects.create(
            tenant=other_tenant,
            competencia="2023-02-01",
            municipio_ibge="3550308",
            valor_servicos="500.00",
            valor_iss="25.00",
            valor_iss_retido="0.00",
        )

        url = reverse("fiscal:livro")
        response = self.client.get(url)
        assert response.status_code == 200
        assert other_livro not in response.context["object_list"]
