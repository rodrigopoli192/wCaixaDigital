import pytest
from django.urls import reverse

from caixa_nfse.tests.factories import TenantFactory, UserFactory


@pytest.mark.django_db
class TestPlatformDashboardView:
    def test_access_denied_for_non_superuser(self, client):
        user = UserFactory(is_staff=True, is_superuser=False)
        client.force_login(user)
        url = reverse("backoffice:dashboard")
        response = client.get(url)
        assert response.status_code == 403  # UserPassesTestMixin default

    def test_access_allowed_superuser(self, client):
        superuser = UserFactory(is_superuser=True, is_staff=True)
        client.force_login(superuser)
        url = reverse("backoffice:dashboard")
        response = client.get(url)
        assert response.status_code == 200
        assert "total_tenants" in response.context


@pytest.mark.django_db
class TestTenantCRUD:
    def setup_method(self):
        from django.test import Client

        self.superuser = UserFactory(is_superuser=True, is_staff=True)
        self.client = Client()
        self.client.force_login(self.superuser)

    def test_update_tenant(self):
        tenant = TenantFactory()
        url = reverse("backoffice:tenant_edit", kwargs={"pk": tenant.pk})
        response = self.client.get(url)
        assert response.status_code == 200
        assert "usuarios" in response.context

        # Test post update
        data = {
            "razao_social": "Updated Corp",
            "nome_fantasia": "UpCorp",
            "cnpj": tenant.cnpj,
            "cidade": "SP",
            "uf": "SP",
            "regime_tributario": "SIMPLES",
            "logradouro": "Rua X",
            "numero": "1",
            "bairro": "Centro",
            "cep": "00000-000",
            "telefone": "11999999999",
            "ativo": True,
        }
        response = self.client.post(url, data)
        assert response.status_code == 302
        tenant.refresh_from_db()
        assert tenant.razao_social == "Updated Corp"

    def test_create_tenant_flow(self):
        url = reverse("backoffice:tenant_add")
        data = {
            "razao_social": "New Corp",
            "nome_fantasia": "NewCorp",
            "cnpj": "11444777000161",
            "cidade": "Rio",
            "uf": "RJ",
            "regime_tributario": "REAL",
            "codigo_ibge": "3304557",
            "logradouro": "Av B",
            "numero": "20",
            "bairro": "Sul",
            "cep": "22000-000",
            "telefone": "21999999999",
            "admin_name": "Sys Admin",
            "admin_email": "sys@newcorp.com",
            "admin_password": "pass",
        }
        response = self.client.post(url, data)
        assert response.status_code == 302  # Redirects to dashboard

    def test_delete_tenant(self):
        tenant = TenantFactory()
        tenant_pk = tenant.pk
        url = reverse("backoffice:tenant_delete", kwargs={"pk": tenant_pk})
        response = self.client.post(url)
        assert response.status_code == 302
        from caixa_nfse.core.models import Tenant

        assert not Tenant.objects.filter(pk=tenant_pk).exists()


@pytest.mark.django_db
class TestTenantUserManagement:
    def setup_method(self):
        from django.test import Client

        self.superuser = UserFactory(is_superuser=True, is_staff=True)
        self.client = Client()
        self.client.force_login(self.superuser)
        self.tenant = TenantFactory()

    def test_add_user_form_view(self):
        url = reverse("backoffice:tenant_user_add", kwargs={"tenant_pk": self.tenant.pk})
        response = self.client.get(url)
        assert response.status_code == 200
        assert "is_new" in response.context
        assert response.context["is_new"] is True

    def test_add_user_htmx(self):
        url = reverse("backoffice:tenant_user_add", kwargs={"tenant_pk": self.tenant.pk})
        data = {
            "email": "newuser@tenant.com",
            "first_name": "New",
            "last_name": "User",
            "password": "123",  # Required
            "cargo": "Caixa",
        }
        response = self.client.post(url, data)
        assert response.status_code == 200
        # Check HTMX response content (div with hx-trigger)
        assert 'hx-trigger="load"' in response.content.decode()

    def test_update_user_htmx(self):
        user = UserFactory(tenant=self.tenant)
        url = reverse(
            "backoffice:tenant_user_edit", kwargs={"tenant_pk": self.tenant.pk, "pk": user.pk}
        )

        # Test Get
        response = self.client.get(url)
        assert response.status_code == 200
        assert response.context["is_new"] is False

        # Test Post Update
        data = {
            "email": user.email,
            "first_name": "Updated",
            "last_name": "Name",
            "cargo": "Gerente",
            # Password empty = keep partial
        }
        response = self.client.post(url, data)
        assert response.status_code == 200
        assert 'hx-trigger="load"' in response.content.decode()

        user.refresh_from_db()
        assert user.first_name == "Updated"


@pytest.mark.django_db
class TestDashboardKPIs:
    def setup_method(self):
        from django.test import Client

        self.superuser = UserFactory(is_superuser=True, is_staff=True)
        self.client = Client()
        self.client.force_login(self.superuser)
        self.url = reverse("backoffice:dashboard")

    def test_kpi_context_keys(self):
        response = self.client.get(self.url)
        assert response.status_code == 200
        ctx = response.context
        for key in [
            "total_tenants",
            "active_tenants",
            "total_users",
            "nfse_emitidas_mes",
            "caixas_abertos",
            "movimentos_importados_mes",
            "atividade_recente",
        ]:
            assert key in ctx, f"Missing key: {key}"

    def test_search_by_name(self):
        TenantFactory(razao_social="Alpha Corp", cnpj="11111111000100")
        TenantFactory(razao_social="Beta Corp", cnpj="22222222000100")
        response = self.client.get(self.url, {"q": "Alpha"})
        assert response.status_code == 200
        tenants = list(response.context["tenants"])
        assert len(tenants) == 1
        assert tenants[0].razao_social == "Alpha Corp"

    def test_search_by_cnpj(self):
        TenantFactory(razao_social="Gamma Corp", cnpj="33333333000100")
        response = self.client.get(self.url, {"q": "33333333"})
        tenants = list(response.context["tenants"])
        assert len(tenants) == 1

    def test_filter_by_status_ativo(self):
        TenantFactory(ativo=True, cnpj="44444444000100")
        TenantFactory(ativo=False, cnpj="55555555000100")
        response = self.client.get(self.url, {"status": "ativo"})
        tenants = list(response.context["tenants"])
        assert all(t.ativo for t in tenants)

    def test_filter_by_status_inativo(self):
        TenantFactory(ativo=True, cnpj="66666666000100")
        TenantFactory(ativo=False, cnpj="77777777000100")
        response = self.client.get(self.url, {"status": "inativo"})
        tenants = list(response.context["tenants"])
        assert all(not t.ativo for t in tenants)

    def test_activity_log_populated(self):
        from caixa_nfse.tests.factories import RegistroAuditoriaFactory

        RegistroAuditoriaFactory()
        response = self.client.get(self.url)
        assert len(response.context["atividade_recente"]) >= 1


@pytest.mark.django_db
class TestTenantHealthCheck:
    def setup_method(self):
        from django.test import Client

        self.superuser = UserFactory(is_superuser=True, is_staff=True)
        self.client = Client()
        self.client.force_login(self.superuser)
        self.tenant = TenantFactory()

    def test_health_check_no_connections(self):
        url = reverse("backoffice:tenant_health_check", kwargs={"tenant_pk": self.tenant.pk})
        response = self.client.post(url)
        assert response.status_code == 200
        assert "Nenhuma conexão" in response.content.decode()

    def test_health_check_with_mock_connection(self):
        from unittest.mock import MagicMock, patch

        from caixa_nfse.core.models import ConexaoExterna

        conexao = ConexaoExterna.objects.create(
            tenant=self.tenant,
            tipo_conexao=ConexaoExterna.TipoConexao.FIREBIRD,
            host="localhost",
            porta=3050,
            database="/test.fdb",
            usuario="SYSDBA",
            senha="masterkey",
        )
        mock_conn = MagicMock()
        with patch(
            "caixa_nfse.core.services.sql_executor.SQLExecutor.get_connection",
            return_value=mock_conn,
        ):
            url = reverse("backoffice:tenant_health_check", kwargs={"tenant_pk": self.tenant.pk})
            response = self.client.post(url)
            assert response.status_code == 200
            assert "Conexão OK" in response.content.decode()
            mock_conn.close.assert_called_once()

    def test_health_check_connection_failure(self):
        from unittest.mock import patch

        from caixa_nfse.core.models import ConexaoExterna

        ConexaoExterna.objects.create(
            tenant=self.tenant,
            tipo_conexao=ConexaoExterna.TipoConexao.MSSQL,
            host="invalid-host",
            porta=1433,
            database="testdb",
            usuario="sa",
            senha="pass",
        )
        with patch(
            "caixa_nfse.core.services.sql_executor.SQLExecutor.get_connection",
            side_effect=Exception("Connection refused"),
        ):
            url = reverse("backoffice:tenant_health_check", kwargs={"tenant_pk": self.tenant.pk})
            response = self.client.post(url)
            assert response.status_code == 200
            content = response.content.decode()
            assert "Connection refused" in content

    def test_access_denied_for_non_superuser(self, client):
        user = UserFactory(is_staff=True, is_superuser=False)
        client.force_login(user)
        url = reverse("backoffice:tenant_health_check", kwargs={"tenant_pk": self.tenant.pk})
        response = client.post(url)
        assert response.status_code == 403
