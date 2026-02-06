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
            "cnpj": "99999999000199",
            "cidade": "Rio",
            "uf": "RJ",
            "regime_tributario": "LUCRO_REAL",
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
        url = reverse("backoffice:tenant_delete", kwargs={"pk": tenant.pk})
        response = self.client.post(url)
        assert response.status_code == 302
        assert not tenant.pk  # Basic delete check, or refresh from db
        # If it's real delete:
        from caixa_nfse.core.models import Tenant

        assert not Tenant.objects.filter(pk=tenant.pk).exists()


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
