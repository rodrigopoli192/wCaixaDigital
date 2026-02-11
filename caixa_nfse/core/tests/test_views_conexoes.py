"""
Tests for Core Views: ConexaoExterna CRUD, Rotinas, UserProfile, SettingsParametros.
Covers lines 267-268, 314, 321, 331, 345, 395, 404-409, 466, 511, 514-521, 524-531,
632, 645, 648-651, 654-659, 672, 675, 678-681, 684-688, 697-703, 712-735, 742-764,
773-827, 838-869 of core/views.py.
"""

import uuid
from unittest.mock import patch

import pytest
from django.urls import reverse

from caixa_nfse.backoffice.models import Rotina, Sistema
from caixa_nfse.conftest import *  # noqa: F401,F403 — reuse shared fixtures
from caixa_nfse.core.models import ConexaoExterna, Tenant

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def sistema(db):
    return Sistema.objects.create(nome="RI Legacy", ativo=True)


@pytest.fixture
def rotina(db, sistema):
    return Rotina.objects.create(
        sistema=sistema,
        nome="Buscar Protocolos",
        sql_content="SELECT * FROM protocolos WHERE data >= @DATA_INICIO",
        ativo=True,
    )


@pytest.fixture
def conexao(db, tenant, sistema):
    return ConexaoExterna.objects.create(
        tenant=tenant,
        sistema=sistema,
        tipo_conexao="MSSQL",
        host="10.0.0.1",
        porta=1433,
        database="DB_RI",
        usuario="sa",
        senha="secret",
    )


@pytest.fixture
def admin_client(client, admin_user):
    client.force_login(admin_user)
    return client


# ===========================================================================
# ConexaoExterna CRUD
# ===========================================================================


@pytest.mark.django_db
class TestConexaoExternaListView:
    def test_list_conexoes(self, admin_client, conexao):
        url = reverse("core:settings_conexoes_list")
        response = admin_client.get(url)
        assert response.status_code == 200
        assert "conexoes" in response.context

    def test_list_filters_by_tenant(self, admin_client, conexao, sistema):
        other_tenant = Tenant.objects.create(
            razao_social="Outra",
            cnpj="98765432000199",
            logradouro="R",
            numero="1",
            bairro="B",
            cidade="C",
            uf="SP",
            cep="00000000",
        )
        ConexaoExterna.objects.create(
            tenant=other_tenant,
            sistema=None,
            tipo_conexao="FIREBIRD",
            host="x",
            porta=1,
            database="x",
            usuario="x",
            senha="x",
        )
        url = reverse("core:settings_conexoes_list")
        response = admin_client.get(url)
        assert len(response.context["conexoes"]) == 1


@pytest.mark.django_db
class TestConexaoExternaCreateView:
    def test_get_form(self, admin_client):
        url = reverse("core:settings_conexao_add")
        response = admin_client.get(url)
        assert response.status_code == 200
        assert response.context["is_edit"] is False

    def test_create_conexao(self, admin_client, sistema):
        url = reverse("core:settings_conexao_add")
        data = {
            "sistema": sistema.pk,
            "tipo_conexao": "MSSQL",
            "host": "192.168.1.1",
            "porta": 1433,
            "database": "TestDB",
            "usuario": "sa",
            "senha": "pass",
            "charset": "WIN1252",
            "instancia": "",
            "ativo": True,
        }
        response = admin_client.post(url, data)
        assert response.status_code == 302
        assert ConexaoExterna.objects.filter(host="192.168.1.1").exists()


@pytest.mark.django_db
class TestConexaoExternaUpdateView:
    def test_get_edit_form(self, admin_client, conexao):
        url = reverse("core:settings_conexao_edit", kwargs={"pk": conexao.pk})
        response = admin_client.get(url)
        assert response.status_code == 200
        assert response.context["is_edit"] is True

    def test_update_conexao(self, admin_client, conexao, sistema):
        url = reverse("core:settings_conexao_edit", kwargs={"pk": conexao.pk})
        data = {
            "sistema": sistema.pk,
            "tipo_conexao": "MSSQL",
            "host": "10.0.0.2",
            "porta": 1433,
            "database": "DB_RI",
            "usuario": "sa",
            "senha": "newsecret",
            "charset": "WIN1252",
            "instancia": "",
            "ativo": True,
        }
        response = admin_client.post(url, data)
        assert response.status_code == 302
        conexao.refresh_from_db()
        assert conexao.host == "10.0.0.2"


@pytest.mark.django_db
class TestConexaoExternaDeleteView:
    def test_delete_conexao(self, admin_client, conexao):
        url = reverse("core:settings_conexao_delete", kwargs={"pk": conexao.pk})
        response = admin_client.post(url)
        assert response.status_code == 200
        conexao.refresh_from_db()
        assert conexao.ativo is False

    def test_delete_not_found(self, admin_client):
        fake_uuid = uuid.uuid4()
        url = reverse("core:settings_conexao_delete", kwargs={"pk": fake_uuid})
        response = admin_client.post(url)
        assert response.status_code == 404


# ===========================================================================
# Rotinas Views
# ===========================================================================


@pytest.mark.django_db
class TestRotinasPorSistemaView:
    def test_no_sistema_returns_empty(self, admin_client):
        url = reverse("core:api_rotinas_por_sistema")
        response = admin_client.get(url)
        assert response.status_code == 200
        assert response.content == b""

    def test_with_sistema(self, admin_client, sistema, rotina):
        url = reverse("core:api_rotinas_por_sistema")
        response = admin_client.get(url, {"sistema": sistema.pk})
        assert response.status_code == 200

    def test_with_conexao_id(self, admin_client, sistema, rotina, conexao):
        conexao.rotinas.add(rotina)
        url = reverse("core:api_rotinas_por_sistema")
        response = admin_client.get(
            url,
            {
                "sistema": sistema.pk,
                "conexao_id": conexao.pk,
            },
        )
        assert response.status_code == 200

    def test_with_invalid_conexao_id(self, admin_client, sistema, rotina):
        url = reverse("core:api_rotinas_por_sistema")
        response = admin_client.get(
            url,
            {
                "sistema": sistema.pk,
                "conexao_id": str(uuid.uuid4()),
            },
        )
        assert response.status_code == 200


@pytest.mark.django_db
class TestRotinasJsonView:
    def test_no_conexao_id(self, admin_client):
        url = reverse("core:api_rotinas_json")
        response = admin_client.get(url)
        assert response.status_code == 200
        assert response.json() == {"rotinas": []}

    def test_invalid_conexao_id(self, admin_client):
        url = reverse("core:api_rotinas_json")
        response = admin_client.get(url, {"conexao_id": str(uuid.uuid4())})
        assert response.status_code == 200
        assert response.json() == {"rotinas": []}

    def test_valid_conexao_with_rotinas(self, admin_client, conexao, rotina):
        conexao.rotinas.add(rotina)
        url = reverse("core:api_rotinas_json")
        response = admin_client.get(url, {"conexao_id": conexao.pk})
        data = response.json()
        assert len(data["rotinas"]) == 1
        assert data["rotinas"][0]["nome"] == "Buscar Protocolos"


@pytest.mark.django_db
class TestRotinaExecutionView:
    def test_get_execution_form(self, admin_client, rotina):
        url = reverse("core:api_rotinas_execucao", kwargs={"pk": rotina.pk})
        response = admin_client.get(url)
        assert response.status_code == 200
        assert "rotina" in response.context
        assert "variables" in response.context

    def test_get_not_found(self, admin_client):
        url = reverse("core:api_rotinas_execucao", kwargs={"pk": 99999})
        response = admin_client.get(url)
        assert response.status_code == 404

    def test_post_no_conexao(self, admin_client, rotina):
        url = reverse("core:api_rotinas_execucao", kwargs={"pk": rotina.pk})
        response = admin_client.post(url, {})
        assert response.status_code == 400

    def test_post_rotina_not_found(self, admin_client):
        url = reverse("core:api_rotinas_execucao", kwargs={"pk": 99999})
        response = admin_client.post(url, {"conexao_id": "1"})
        assert response.status_code == 404

    def test_post_conexao_not_found(self, admin_client, rotina):
        url = reverse("core:api_rotinas_execucao", kwargs={"pk": rotina.pk})
        response = admin_client.post(url, {"conexao_id": str(uuid.uuid4())})
        assert response.status_code == 404

    @patch("caixa_nfse.core.services.sql_executor.SQLExecutor.execute_routine")
    def test_post_success(self, mock_exec, admin_client, rotina, conexao):
        mock_exec.return_value = (["col1"], [["val1"]], ["log1"])
        url = reverse("core:api_rotinas_execucao", kwargs={"pk": rotina.pk})
        response = admin_client.post(
            url,
            {
                "conexao_id": str(conexao.pk),
                "DATA_INICIO": "20260101",
            },
        )
        assert response.status_code == 200
        mock_exec.assert_called_once()

    @patch("caixa_nfse.core.services.sql_executor.SQLExecutor.execute_routine")
    def test_post_execution_error(self, mock_exec, admin_client, rotina, conexao):
        mock_exec.side_effect = Exception("Connection refused")
        url = reverse("core:api_rotinas_execucao", kwargs={"pk": rotina.pk})
        response = admin_client.post(
            url,
            {
                "conexao_id": str(conexao.pk),
                "DATA_INICIO": "20260101",
            },
        )
        assert response.status_code == 500
        assert "Connection refused" in response.content.decode()


# ===========================================================================
# UserProfile & Password
# ===========================================================================


@pytest.mark.django_db
class TestUserProfileView:
    def test_get_profile(self, admin_client):
        url = reverse("core:user_profile")
        response = admin_client.get(url)
        assert response.status_code == 200

    def test_update_profile(self, admin_client, admin_user):
        url = reverse("core:user_profile")
        response = admin_client.post(
            url,
            {
                "first_name": "Novo",
                "last_name": "Nome",
                "cpf": "",
            },
        )
        assert response.status_code == 200
        assert response["HX-Trigger"] == "profileUpdated"
        admin_user.refresh_from_db()
        assert admin_user.first_name == "Novo"


@pytest.mark.django_db
class TestUserPasswordChangeView:
    def test_get_form(self, admin_client):
        url = reverse("core:user_change_password")
        response = admin_client.get(url)
        assert response.status_code == 200

    def test_change_password_success(self, admin_client, admin_user):
        url = reverse("core:user_change_password")
        response = admin_client.post(
            url,
            {
                "old_password": "adminpass123",
                "new_password1": "newSecure!456",
                "new_password2": "newSecure!456",
            },
        )
        assert response.status_code == 200
        assert response["HX-Trigger"] == "passwordChanged"

    def test_change_password_wrong_old(self, admin_client):
        url = reverse("core:user_change_password")
        response = admin_client.post(
            url,
            {
                "old_password": "wrong",
                "new_password1": "newSecure!456",
                "new_password2": "newSecure!456",
            },
        )
        assert response.status_code == 200
        assert "form" in response.context


# ===========================================================================
# Settings Parametros
# ===========================================================================


@pytest.mark.django_db
class TestSettingsParametrosView:
    def test_get_parametros(self, admin_client):
        url = reverse("core:settings_parametros")
        response = admin_client.get(url)
        assert response.status_code == 200
        assert "tenant" in response.context

    def test_post_parametros(self, admin_client, tenant):
        url = reverse("core:settings_parametros")
        response = admin_client.post(
            url,
            {
                "chave_servico_andamento_ri": "ABC123",
            },
        )
        assert response.status_code == 200
        tenant.refresh_from_db()
        assert tenant.chave_servico_andamento_ri == "ABC123"


# ===========================================================================
# ConexaoExterna Test Connection
# ===========================================================================


@pytest.mark.django_db
class TestConexaoExternaTestView:
    def test_missing_fields(self, admin_client):
        url = reverse("core:settings_conexao_test")
        response = admin_client.post(
            url,
            {
                "sistema": "RI",
                "tipo_conexao": "MSSQL",
                "host": "",
                "porta": "",
                "usuario": "",
                "senha": "",
            },
        )
        data = response.json()
        assert data["status"] == "error"

    def test_invalid_port(self, admin_client):
        url = reverse("core:settings_conexao_test")
        response = admin_client.post(
            url,
            {
                "sistema": "RI",
                "tipo_conexao": "MSSQL",
                "host": "localhost",
                "porta": "abc",
                "database": "test",
                "usuario": "sa",
                "senha": "pass",
            },
        )
        data = response.json()
        assert data["status"] == "error"
        assert "Porta inválida" in data["message"]

    @patch("socket.create_connection")
    def test_tcp_failure(self, mock_sock, admin_client):
        mock_sock.side_effect = OSError("Connection refused")
        url = reverse("core:settings_conexao_test")
        response = admin_client.post(
            url,
            {
                "sistema": "RI",
                "tipo_conexao": "MSSQL",
                "host": "10.0.0.1",
                "porta": "1433",
                "database": "test",
                "usuario": "sa",
                "senha": "pass",
            },
        )
        data = response.json()
        assert data["status"] == "error"
        assert "TCP" in data["message"]

    @patch("socket.create_connection")
    def test_tcp_success_mssql_no_driver(self, mock_sock, admin_client):
        mock_sock.return_value.close.return_value = None
        url = reverse("core:settings_conexao_test")
        with patch.dict("sys.modules", {"pymssql": None}):
            response = admin_client.post(
                url,
                {
                    "sistema": "RI",
                    "tipo_conexao": "MSSQL",
                    "host": "10.0.0.1",
                    "porta": "1433",
                    "database": "test",
                    "usuario": "sa",
                    "senha": "pass",
                },
            )
        data = response.json()
        assert data["status"] == "success"

    @patch("socket.create_connection")
    def test_tcp_success_postgres_no_driver(self, mock_sock, admin_client):
        mock_sock.return_value.close.return_value = None
        url = reverse("core:settings_conexao_test")
        with patch.dict("sys.modules", {"psycopg": None}):
            response = admin_client.post(
                url,
                {
                    "sistema": "RI",
                    "tipo_conexao": "POSTGRES",
                    "host": "10.0.0.1",
                    "porta": "5432",
                    "database": "test",
                    "usuario": "postgres",
                    "senha": "pass",
                },
            )
        data = response.json()
        assert data["status"] == "success"

    @patch("socket.create_connection")
    def test_tcp_success_firebird_no_driver(self, mock_sock, admin_client):
        mock_sock.return_value.close.return_value = None
        url = reverse("core:settings_conexao_test")
        with patch.dict("sys.modules", {"fdb": None}):
            response = admin_client.post(
                url,
                {
                    "sistema": "RI",
                    "tipo_conexao": "FIREBIRD",
                    "host": "10.0.0.1",
                    "porta": "3050",
                    "database": "/opt/firebird/test.fdb",
                    "usuario": "SYSDBA",
                    "senha": "masterkey",
                },
            )
        data = response.json()
        assert data["status"] == "success"
