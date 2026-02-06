import pytest

from caixa_nfse.backoffice.forms import TenantOnboardingForm, TenantUserForm
from caixa_nfse.tests.factories import TenantFactory, UserFactory


@pytest.mark.django_db
class TestTenantOnboardingForm:
    def test_create_tenant_and_admin(self):
        data = {
            "razao_social": "Company One",
            "nome_fantasia": "Comp1",
            "cnpj": "12345678000199",
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
