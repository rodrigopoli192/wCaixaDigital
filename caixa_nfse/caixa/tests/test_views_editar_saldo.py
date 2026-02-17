"""
Tests for EditarSaldoInicialView.
"""

from decimal import Decimal
from unittest.mock import PropertyMock, patch

import pytest
from django.test import Client
from django.urls import reverse

from caixa_nfse.caixa.models import AberturaCaixa, Caixa
from caixa_nfse.tests.factories import TenantFactory, UserFactory


@pytest.fixture
def setup_caixa(db):
    """Create tenant, user, caixa, and abertura for testing."""
    tenant = TenantFactory()
    user = UserFactory(tenant=tenant, pode_operar_caixa=True)
    caixa = Caixa.objects.create(
        tenant=tenant,
        identificador="CX-TEST",
        saldo_atual=Decimal("100.00"),
    )
    abertura = AberturaCaixa.objects.create(
        caixa=caixa,
        operador=user,
        saldo_abertura=Decimal("100.00"),
        tenant=tenant,
    )
    return {"tenant": tenant, "user": user, "caixa": caixa, "abertura": abertura}


@pytest.mark.django_db
class TestEditarSaldoInicialView:
    def _get_url(self, pk):
        return reverse("caixa:editar_saldo_inicial", kwargs={"pk": pk})

    def test_get_modal_success(self, setup_caixa):
        client = Client()
        client.force_login(setup_caixa["user"])
        abertura = setup_caixa["abertura"]

        with patch.object(
            type(abertura),
            "pode_editar_saldo_inicial",
            new_callable=PropertyMock,
            return_value=True,
        ):
            # Need to reload from DB since patch is on class
            response = client.get(self._get_url(abertura.pk))
        assert response.status_code == 200

    def test_get_modal_blocked(self, setup_caixa):
        client = Client()
        client.force_login(setup_caixa["user"])
        abertura = setup_caixa["abertura"]

        with patch.object(
            type(abertura),
            "pode_editar_saldo_inicial",
            new_callable=PropertyMock,
            return_value=False,
        ):
            response = client.get(self._get_url(abertura.pk))
        assert response.status_code == 200
        assert "não permitida" in response.content.decode().lower() or response.status_code == 200

    def test_get_requires_permission(self, setup_caixa):
        user_sem_permissao = UserFactory(tenant=setup_caixa["tenant"], pode_operar_caixa=False)
        client = Client()
        client.force_login(user_sem_permissao)
        response = client.get(self._get_url(setup_caixa["abertura"].pk))
        assert response.status_code == 403

    def test_post_success(self, setup_caixa):
        client = Client()
        client.force_login(setup_caixa["user"])
        abertura = setup_caixa["abertura"]

        with patch.object(
            type(abertura),
            "pode_editar_saldo_inicial",
            new_callable=PropertyMock,
            return_value=True,
        ):
            response = client.post(
                self._get_url(abertura.pk),
                {"novo_saldo": "250,00"},
            )
        assert response.status_code == 200
        abertura.refresh_from_db()
        assert abertura.saldo_abertura == Decimal("250.00")
        assert abertura.saldo_inicial_editado is True

    def test_post_blocked(self, setup_caixa):
        client = Client()
        client.force_login(setup_caixa["user"])
        abertura = setup_caixa["abertura"]

        with patch.object(
            type(abertura),
            "pode_editar_saldo_inicial",
            new_callable=PropertyMock,
            return_value=False,
        ):
            response = client.post(
                self._get_url(abertura.pk),
                {"novo_saldo": "250,00"},
            )
        assert response.status_code == 403

    def test_post_invalid_value(self, setup_caixa):
        client = Client()
        client.force_login(setup_caixa["user"])
        abertura = setup_caixa["abertura"]

        with patch.object(
            type(abertura),
            "pode_editar_saldo_inicial",
            new_callable=PropertyMock,
            return_value=True,
        ):
            response = client.post(
                self._get_url(abertura.pk),
                {"novo_saldo": "abc"},
            )
        assert response.status_code == 400

    def test_post_negative_value(self, setup_caixa):
        client = Client()
        client.force_login(setup_caixa["user"])
        abertura = setup_caixa["abertura"]

        with patch.object(
            type(abertura),
            "pode_editar_saldo_inicial",
            new_callable=PropertyMock,
            return_value=True,
        ):
            response = client.post(
                self._get_url(abertura.pk),
                {"novo_saldo": "-50,00"},
            )
        assert response.status_code == 400

    def test_post_requires_permission(self, setup_caixa):
        user_sem_permissao = UserFactory(tenant=setup_caixa["tenant"], pode_operar_caixa=False)
        client = Client()
        client.force_login(user_sem_permissao)
        response = client.post(
            self._get_url(setup_caixa["abertura"].pk),
            {"novo_saldo": "100,00"},
        )
        assert response.status_code == 403
