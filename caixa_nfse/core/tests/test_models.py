import datetime

import pytest
from django.db import IntegrityError
from django.utils import timezone

from caixa_nfse.core.models import RegimeTributario, Tenant, User, generate_hash
from caixa_nfse.tests.factories import FormaPagamentoFactory, TenantFactory, UserFactory


@pytest.mark.django_db
class TestTenantModel:
    """Tests for Tenant model."""

    def test_create_tenant(self):
        """Should create tenant with defaults."""
        tenant = TenantFactory()
        assert tenant.pk is not None
        assert tenant.regime_tributario == RegimeTributario.SIMPLES
        assert str(tenant) == f"{tenant.razao_social} ({tenant.cnpj})"

    def test_endereco_completo(self):
        """Should return formatted address."""
        tenant = TenantFactory(
            logradouro="Rua A",
            numero="10",
            complemento="",
            bairro="Centro",
            cidade="Cidade X",
            uf="SP",
            cep="12345678",
        )
        expected = "Rua A, 10, Centro, Cidade X/SP, 12345678"
        assert tenant.endereco_completo == expected

    def test_endereco_completo_with_complemento(self):
        """Should include complement in address."""
        tenant = TenantFactory(complemento="Apto 1")
        assert "Apto 1" in tenant.endereco_completo

    def test_certificado_validity(self):
        """Should check certificate validity."""
        tenant = TenantFactory(certificado_validade=None)
        assert tenant.certificado_valido is False

        tenant.certificado_validade = timezone.now().date() + datetime.timedelta(days=1)
        assert tenant.certificado_valido is True

        tenant.certificado_validade = timezone.now().date() - datetime.timedelta(days=1)
        assert tenant.certificado_valido is False

    def test_proximo_numero_rps(self):
        """Should increment RPS number atomically."""
        tenant = TenantFactory(nfse_ultimo_rps=10)
        assert tenant.proximo_numero_rps() == 11
        tenant.refresh_from_db()
        assert tenant.nfse_ultimo_rps == 11


@pytest.mark.django_db
class TestUserModel:
    """Tests for User model."""

    def test_create_user(self):
        """Should create user with email as username."""
        user = UserFactory(email="john@test.com", first_name="John", last_name="Doe")
        assert user.pk is not None
        assert str(user) == "John Doe"
        assert user.get_full_name() == "John Doe"

    def test_create_user_no_email(self):
        """Should fail if email is missing."""
        with pytest.raises(ValueError):
            User.objects.create_user(email="")

    def test_create_superuser(self):
        """Should create superuser with permissions."""
        admin = User.objects.create_superuser(email="admin@test.com", password="123")
        assert admin.is_staff
        assert admin.is_superuser

    def test_create_superuser_validation(self):
        """Should check superuser flags."""
        with pytest.raises(ValueError, match="Superuser deve ter is_staff=True"):
            User.objects.create_superuser(email="a@a.com", password="123", is_staff=False)

        with pytest.raises(ValueError, match="Superuser deve ter is_superuser=True"):
            User.objects.create_superuser(email="b@b.com", password="123", is_superuser=False)


@pytest.mark.django_db
class TestFormaPagamentoModel:
    """Tests for FormaPagamento model."""

    def test_create_forma_pagamento(self):
        """Should create payment method."""
        fp = FormaPagamentoFactory(nome="Dinheiro", tipo="DINHEIRO")
        assert str(fp) == "Dinheiro (Dinheiro)"
        assert fp.pk is not None

    def test_str_representation(self):
        """Should return formatted string."""
        fp = FormaPagamentoFactory(nome="Pix", tipo="PIX")
        assert str(fp) == "Pix (PIX)"

    def test_unique_name_per_tenant(self):
        """Should enforce unique name per tenant."""
        t1 = TenantFactory()
        FormaPagamentoFactory(tenant=t1, nome="Pix")

        with pytest.raises(IntegrityError):
            FormaPagamentoFactory(tenant=t1, nome="Pix")


@pytest.mark.django_db
class TestCoreUtils:
    """Tests for utility functions."""

    def test_generate_hash(self):
        """Should generate SHA-256 hash."""
        data = {"a": 1}
        h1 = generate_hash(data)
        h2 = generate_hash(data)
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex digest length

    def test_tenant_manager_all_with_inactive(self):
        """Should return all tenants including inactive."""
        t1 = TenantFactory(ativo=True)
        t2 = TenantFactory(ativo=False)

        active = Tenant.objects.all()
        assert t1 in active
        assert t2 not in active

        all_tenants = Tenant.objects.all_with_inactive()
        assert t1 in all_tenants
        assert t2 in all_tenants

    def test_generate_hash_chain(self):
        """Should be influenced by previous hash."""
        data = {"a": 1}
        h1 = generate_hash(data, previous_hash="abc")
        h2 = generate_hash(data, previous_hash="def")
        assert h1 != h2
