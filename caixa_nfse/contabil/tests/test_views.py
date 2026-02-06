import pytest
from django.urls import reverse

from caixa_nfse.tests.factories import (
    LancamentoContabilFactory,
    PartidaLancamentoFactory,
    PlanoContasFactory,
    TenantFactory,
)


@pytest.fixture
def plano_contas(tenant):
    return PlanoContasFactory(tenant=tenant)


@pytest.fixture
def lancamento(tenant):
    lancamento_obj = LancamentoContabilFactory(tenant=tenant)
    PartidaLancamentoFactory(lancamento=lancamento_obj, tipo="D", valor="100.00")
    PartidaLancamentoFactory(lancamento=lancamento_obj, tipo="C", valor="100.00")
    return lancamento_obj


@pytest.mark.django_db
class TestPlanoContasListView:
    """Tests for PlanoContasListView."""

    def test_list_plano_contas(self, client_logged, plano_contas):
        """Should list accounts for tenant."""
        url = reverse("contabil:plano_contas")
        response = client_logged.get(url)
        assert response.status_code == 200
        assert plano_contas in response.context["object_list"]

    def test_filter_tenant(self, client_logged):
        """Should not show accounts from other tenants."""
        other_tenant = TenantFactory()
        other_conta = PlanoContasFactory(tenant=other_tenant, codigo="9.99")

        url = reverse("contabil:plano_contas")
        response = client_logged.get(url)
        assert response.status_code == 200
        assert other_conta not in response.context["object_list"]

    def test_access_without_tenant(self, client):
        """Should return empty list for user without tenant."""
        from caixa_nfse.tests.factories import UserFactory

        user_no_tenant = UserFactory(tenant=None)
        client.force_login(user_no_tenant)

        url = reverse("contabil:plano_contas")
        response = client.get(url)

        assert response.status_code == 200
        assert len(response.context["object_list"]) == 0


@pytest.mark.django_db
class TestLancamentoListView:
    """Tests for LancamentoListView."""

    def test_list_lancamentos(self, client_logged, lancamento):
        """Should list entries for tenant."""
        url = reverse("contabil:lancamento_list")
        response = client_logged.get(url)
        assert response.status_code == 200
        assert lancamento in response.context["object_list"]


@pytest.mark.django_db
class TestLancamentoDetailView:
    """Tests for LancamentoDetailView."""

    def test_detail_lancamento(self, client_logged, lancamento):
        """Should show entry details."""
        url = reverse("contabil:lancamento_detail", kwargs={"pk": lancamento.pk})
        response = client_logged.get(url)
        assert response.status_code == 200
        assert response.context["object"] == lancamento


@pytest.mark.django_db
class TestExportarLancamentosView:
    """Tests on CSV export."""

    def test_export_csv(self, client_logged, lancamento):
        """Should return CSV file with entries."""
        url = reverse("contabil:exportar_lancamentos")
        response = client_logged.get(url)
        assert response.status_code == 200
        assert response["Content-Type"] == "text/csv"
        assert 'attachment; filename="lancamentos.csv"' in response["Content-Disposition"]

        content = response.content.decode("utf-8")
        assert "Data,Competência,Documento,Histórico,Conta,D/C,Valor" in content
        assert lancamento.historico in content
        assert "100.00" in content
