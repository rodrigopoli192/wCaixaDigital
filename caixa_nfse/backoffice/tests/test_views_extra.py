"""
Tests for Backoffice views: Sistema CRUD + Rotina CRUD.
Covers backoffice/views.py lines: 180-183, 190-200, 215-228, 236-239,
245-260, 262-275, 281-301, 303-315, 321-327.
"""

import pytest
from django.urls import reverse

from caixa_nfse.backoffice.models import Rotina, Sistema
from caixa_nfse.conftest import *  # noqa: F401,F403

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def superuser_client(client, db):
    from caixa_nfse.core.models import Tenant, User

    tenant = Tenant.objects.create(
        razao_social="Platform",
        cnpj="11222333000181",
        logradouro="R",
        numero="1",
        bairro="B",
        cidade="C",
        uf="SP",
        cep="00000000",
    )
    user = User.objects.create_superuser(
        email="platform@test.com",
        password="superpass123",
        tenant=tenant,
    )
    client.force_login(user)
    return client


@pytest.fixture
def sistema(db):
    return Sistema.objects.create(nome="RI Legacy", ativo=True)


@pytest.fixture
def rotina(db, sistema):
    return Rotina.objects.create(
        sistema=sistema,
        nome="Buscar Protocolos",
        sql_content="SELECT * FROM protocolos",
        ativo=True,
    )


# ===========================================================================
# Sistema CRUD
# ===========================================================================


@pytest.mark.django_db
class TestSistemaListView:
    def test_list(self, superuser_client, sistema):
        url = reverse("backoffice:sistema_list")
        response = superuser_client.get(url)
        assert response.status_code == 200
        assert "sistemas" in response.context


@pytest.mark.django_db
class TestSistemaCreateView:
    def test_get_form(self, superuser_client):
        url = reverse("backoffice:sistema_add")
        response = superuser_client.get(url)
        assert response.status_code == 200

    def test_create_sistema(self, superuser_client):
        url = reverse("backoffice:sistema_add")
        response = superuser_client.post(
            url,
            {"nome": "Novo Sistema", "ativo": True},
        )
        assert response.status_code == 200
        assert Sistema.objects.filter(nome="Novo Sistema").exists()


@pytest.mark.django_db
class TestSistemaUpdateView:
    def test_get_edit_form(self, superuser_client, sistema):
        url = reverse("backoffice:sistema_edit", kwargs={"pk": sistema.pk})
        response = superuser_client.get(url)
        assert response.status_code == 200
        assert "sistema" in response.context
        assert "rotinas" in response.context

    def test_update_sistema(self, superuser_client, sistema):
        url = reverse("backoffice:sistema_edit", kwargs={"pk": sistema.pk})
        response = superuser_client.post(
            url,
            {"nome": "RI Atualizado", "ativo": True},
        )
        assert response.status_code == 302
        sistema.refresh_from_db()
        assert sistema.nome == "RI Atualizado"


@pytest.mark.django_db
class TestSistemaDeleteView:
    def test_get_confirm(self, superuser_client, sistema):
        url = reverse("backoffice:sistema_delete", kwargs={"pk": sistema.pk})
        response = superuser_client.get(url)
        assert response.status_code == 200

    def test_delete_sistema(self, superuser_client, sistema):
        url = reverse("backoffice:sistema_delete", kwargs={"pk": sistema.pk})
        response = superuser_client.post(url)
        assert response.status_code == 302
        assert not Sistema.objects.filter(pk=sistema.pk).exists()


# ===========================================================================
# Rotina CRUD
# ===========================================================================


@pytest.mark.django_db
class TestRotinaCreateView:
    def test_get_form(self, superuser_client, sistema):
        url = reverse("backoffice:rotina_add", kwargs={"sistema_pk": sistema.pk})
        response = superuser_client.get(url)
        assert response.status_code == 200
        assert "sistema" in response.context
        assert "mapeamento_formset" in response.context

    def test_create_rotina(self, superuser_client, sistema):
        url = reverse("backoffice:rotina_add", kwargs={"sistema_pk": sistema.pk})
        response = superuser_client.post(
            url,
            {
                "nome": "Nova Rotina",
                "sql_content": "SELECT 1",
                "ativo": True,
                # Inline formset management fields
                "mapeamento_set-TOTAL_FORMS": "0",
                "mapeamento_set-INITIAL_FORMS": "0",
                "mapeamento_set-MIN_NUM_FORMS": "0",
                "mapeamento_set-MAX_NUM_FORMS": "1000",
            },
        )
        assert response.status_code == 200
        assert Rotina.objects.filter(nome="Nova Rotina", sistema=sistema).exists()


@pytest.mark.django_db
class TestRotinaUpdateView:
    def test_get_edit_form(self, superuser_client, rotina):
        url = reverse("backoffice:rotina_edit", kwargs={"pk": rotina.pk})
        response = superuser_client.get(url)
        assert response.status_code == 200
        assert "mapeamento_formset" in response.context

    def test_update_rotina(self, superuser_client, rotina):
        url = reverse("backoffice:rotina_edit", kwargs={"pk": rotina.pk})
        response = superuser_client.post(
            url,
            {
                "nome": "Rotina Atualizada",
                "sql_content": "SELECT 2",
                "ativo": True,
                "mapeamento_set-TOTAL_FORMS": "0",
                "mapeamento_set-INITIAL_FORMS": "0",
                "mapeamento_set-MIN_NUM_FORMS": "0",
                "mapeamento_set-MAX_NUM_FORMS": "1000",
            },
        )
        assert response.status_code == 200
        rotina.refresh_from_db()
        assert rotina.nome == "Rotina Atualizada"


@pytest.mark.django_db
class TestRotinaDeleteView:
    def test_get_confirm(self, superuser_client, rotina):
        url = reverse("backoffice:rotina_delete", kwargs={"pk": rotina.pk})
        response = superuser_client.get(url)
        assert response.status_code == 200

    def test_delete_rotina(self, superuser_client, rotina):
        url = reverse("backoffice:rotina_delete", kwargs={"pk": rotina.pk})
        response = superuser_client.post(url)
        assert response.status_code == 302
        assert not Rotina.objects.filter(pk=rotina.pk).exists()
