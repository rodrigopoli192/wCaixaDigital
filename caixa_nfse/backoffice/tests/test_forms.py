from unittest.mock import MagicMock, patch

import pytest
from django.test import RequestFactory

from caixa_nfse.backoffice.forms import TenantOnboardingForm, TenantUserForm
from caixa_nfse.backoffice.views import CnpjLookupView
from caixa_nfse.tests.factories import TenantFactory, UserFactory


@pytest.mark.django_db
class TestTenantOnboardingForm:
    def test_create_tenant_and_admin(self):
        data = {
            "razao_social": "Company One",
            "nome_fantasia": "Comp1",
            "cnpj": "12345678000199",
            "inscricao_municipal": "123456",
            "codigo_ibge": "3550308",
            "cnae_principal": "6911701",
            "cidade": "São Paulo",
            "uf": "SP",
            "regime_tributario": "SIMPLES",
            "logradouro": "Rua A",
            "numero": "10",
            "bairro": "Centro",
            "cep": "01000-000",
            "telefone": "11999999999",
            "admin_name": "Admin User",
            "admin_email": "admin@company.com",
            "admin_password": "securepassword123",
        }
        form = TenantOnboardingForm(data=data)
        assert form.is_valid(), form.errors
        tenant = form.save()

        # Check Tenant created
        assert tenant.razao_social == "Company One"
        assert tenant.ativo is True
        assert tenant.cnae_principal == "6911701"
        assert tenant.codigo_ibge == "3550308"
        assert tenant.inscricao_municipal == "123456"

        # Check Admin created
        assert tenant.usuarios.count() == 1
        user = tenant.usuarios.first()
        assert user.email == "admin@company.com"
        assert user.check_password("securepassword123")
        assert user.pode_operar_caixa is True


@pytest.mark.django_db
class TestTenantUserForm:
    def test_create_user_requires_password(self):
        tenant = TenantFactory()
        data = {
            "email": "user@test.com",
            "first_name": "User",
            "last_name": "Test",
            "cargo": "Vendedor",
            "is_active": True,
            # No password provided
        }
        form = TenantUserForm(data=data, tenant=tenant)
        assert not form.is_valid()
        assert "password" in form.errors

    def test_update_user_password_optional(self):
        tenant = TenantFactory()
        user = UserFactory(tenant=tenant)
        data = {
            "email": user.email,
            "first_name": "Updated",
            "last_name": "Name",
            "cargo": "Gerente",
            "is_active": True,
            "password": "",  # Empty password
        }
        form = TenantUserForm(data=data, instance=user, tenant=tenant)
        assert form.is_valid(), form.errors
        saved_user = form.save()
        assert saved_user.first_name == "Updated"
        # Password shouldn't change


@pytest.mark.django_db
class TestCnpjLookupView:
    def _make_request(self, cnpj=""):
        factory = RequestFactory()
        request = factory.get(f"/backoffice/api/cnpj-lookup/?cnpj={cnpj}")
        request.user = UserFactory(is_superuser=True, is_staff=True)
        return request

    def test_invalid_cnpj_returns_400(self):
        request = self._make_request("123")
        response = CnpjLookupView.as_view()(request)
        assert response.status_code == 400

    def test_empty_cnpj_returns_400(self):
        request = self._make_request("")
        response = CnpjLookupView.as_view()(request)
        assert response.status_code == 400

    @patch("caixa_nfse.backoffice.views.requests.get")
    def test_successful_lookup(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "razao_social": "Empresa Teste SA",
            "nome_fantasia": "Teste",
            "logradouro": "Rua Principal",
            "numero": "42",
            "bairro": "Centro",
            "municipio": "São Paulo",
            "uf": "SP",
            "cep": "01001000",
            "ddd_telefone_1": "1133334444",
            "cnae_fiscal": 6911701,
            "codigo_municipio_ibge": 3550308,
        }
        mock_get.return_value = mock_response

        request = self._make_request("12345678000199")
        response = CnpjLookupView.as_view()(request)

        assert response.status_code == 200
        import json

        data = json.loads(response.content)
        assert data["razao_social"] == "Empresa Teste SA"
        assert data["cnae_principal"] == "6911701"
        assert data["codigo_ibge"] == "3550308"
        assert data["cidade"] == "São Paulo"

    @patch("caixa_nfse.backoffice.views.requests.get")
    def test_api_failure_returns_502(self, mock_get):
        import requests as req

        mock_get.side_effect = req.ConnectionError("Connection error")

        request = self._make_request("12345678000199")
        response = CnpjLookupView.as_view()(request)

        assert response.status_code == 502
