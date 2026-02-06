"""
Shared test fixtures for wCaixaDigital.
"""

from decimal import Decimal

import pytest


@pytest.fixture
def tenant(db):
    """Create a test tenant."""
    from caixa_nfse.core.models import Tenant

    return Tenant.objects.create(
        razao_social="Empresa Teste Ltda",
        nome_fantasia="Empresa Teste",
        cnpj="12345678000199",
        inscricao_municipal="123456",
        email="teste@empresa.com",
        telefone="11999999999",
        logradouro="Rua Teste",
        numero="100",
        bairro="Centro",
        cidade="São Paulo",
        uf="SP",
        cep="01001000",
    )


@pytest.fixture
def user(db, tenant):
    """Create a test user with operator permissions."""
    from caixa_nfse.core.models import User

    user = User.objects.create_user(
        email="operador@teste.com",
        password="testpass123",
        first_name="Operador",
        last_name="Teste",
        tenant=tenant,
        pode_operar_caixa=True,
    )
    return user


@pytest.fixture
def admin_user(db, tenant):
    """Create a test admin user."""
    from caixa_nfse.core.models import User

    return User.objects.create_user(
        email="admin@teste.com",
        password="adminpass123",
        first_name="Admin",
        last_name="Teste",
        tenant=tenant,
        is_staff=True,
        pode_operar_caixa=True,
        pode_aprovar_fechamento=True,
    )


@pytest.fixture
def caixa(db, tenant):
    """Create a test cash register."""
    from caixa_nfse.caixa.models import Caixa

    return Caixa.objects.create(
        tenant=tenant,
        identificador="CAIXA-01",
        tipo="FISICO",
    )


@pytest.fixture
def forma_pagamento(db, tenant):
    """Create a test payment method."""
    from caixa_nfse.core.models import FormaPagamento

    return FormaPagamento.objects.create(
        tenant=tenant,
        nome="Dinheiro",
        ativo=True,
    )


@pytest.fixture
def abertura(db, caixa, user):
    """Create an open cash register session."""
    from caixa_nfse.caixa.models import AberturaCaixa

    # Ensure user tenant matches caixa tenant
    user.tenant = caixa.tenant
    user.save()

    return AberturaCaixa.objects.create(
        tenant=caixa.tenant,  # Required by TenantAwareModel
        caixa=caixa,
        operador=user,
        saldo_abertura=Decimal("100.00"),
        fundo_troco=Decimal("50.00"),
    )


@pytest.fixture
def client_logged(client, user):
    """Return a logged-in test client."""
    client.force_login(user)
    return client
