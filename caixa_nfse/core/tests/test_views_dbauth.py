"""
Tests for Core views: DB auth test connection (Postgres, Firebird, MSSQL),
operator dashboard, and remaining uncovered lines.
Covers core/views.py lines: 267-268, 314, 321, 331, 345, 808, 849,
936-943, 949-951, 965-976, 979-981, 996-1015, 1018-1020.
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.urls import reverse

from caixa_nfse.caixa.models import AberturaCaixa, Caixa, StatusCaixa
from caixa_nfse.conftest import *  # noqa: F401,F403
from caixa_nfse.core.models import User

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def operator_user(db, tenant):
    return User.objects.create_user(
        email="operator@test.com",
        password="operpass123",
        tenant=tenant,
        pode_operar_caixa=True,
        pode_emitir_nfse=False,
        pode_aprovar_fechamento=False,
    )


@pytest.fixture
def operator_client(client, operator_user):
    client.force_login(operator_user)
    return client


@pytest.fixture
def admin_client(client, admin_user):
    client.force_login(admin_user)
    return client


@pytest.fixture
def caixa_aberto(db, tenant, operator_user):
    return Caixa.objects.create(
        tenant=tenant,
        identificador="CX-OP",
        tipo="FISICO",
        status=StatusCaixa.ABERTO,
        operador_atual=operator_user,
        saldo_atual=Decimal("200.00"),
    )


@pytest.fixture
def abertura(db, tenant, operator_user, caixa_aberto):
    return AberturaCaixa.objects.create(
        tenant=tenant,
        caixa=caixa_aberto,
        operador=operator_user,
        saldo_abertura=Decimal("200.00"),
        created_by=operator_user,
    )


# ===========================================================================
# Operator Dashboard
# ===========================================================================


@pytest.mark.django_db
class TestOperatorDashboard:
    def test_operator_no_caixas(self, operator_client):
        """When operator has no caixas assigned, should see empty state (lines 267-268)."""
        url = reverse("core:dashboard")
        response = operator_client.get(url)
        assert response.status_code == 200

    def test_operator_with_abertura(self, operator_client, abertura, caixa_aberto):
        url = reverse("core:dashboard")
        response = operator_client.get(url)
        assert response.status_code == 200


# ===========================================================================
# DB Auth Test Connection Views
# ===========================================================================


@pytest.mark.django_db
class TestConexaoTestDBAuth:
    """Test the DB authentication path in ConexaoExternaTestView (lines 930-1020)."""

    @patch("socket.create_connection")
    def test_postgres_auth_success(self, mock_sock, admin_client):
        mock_sock.return_value.close.return_value = None

        # Mock psycopg module
        mock_psycopg = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ["PostgreSQL 16.0"]
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_cursor_ctx = MagicMock()
        mock_cursor_ctx.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor_ctx.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value = mock_cursor_ctx
        mock_psycopg.connect.return_value = mock_conn

        url = reverse("core:settings_conexao_test")
        with patch.dict("sys.modules", {"psycopg": mock_psycopg}):
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
        assert "Autenticação OK" in data["message"]

    @patch("socket.create_connection")
    def test_postgres_auth_failure(self, mock_sock, admin_client):
        mock_sock.return_value.close.return_value = None

        mock_psycopg = MagicMock()
        mock_psycopg.connect.side_effect = Exception("password authentication failed")

        url = reverse("core:settings_conexao_test")
        with patch.dict("sys.modules", {"psycopg": mock_psycopg}):
            response = admin_client.post(
                url,
                {
                    "sistema": "RI",
                    "tipo_conexao": "POSTGRES",
                    "host": "10.0.0.1",
                    "porta": "5432",
                    "database": "test",
                    "usuario": "postgres",
                    "senha": "wrong",
                },
            )
        data = response.json()
        assert data["status"] == "error"
        assert "autenticação" in data["message"].lower()

    @patch("socket.create_connection")
    def test_firebird_auth_success(self, mock_sock, admin_client):
        mock_sock.return_value.close.return_value = None

        mock_fdb = MagicMock()
        mock_conn = MagicMock()
        mock_conn.db_info.return_value = "12.0"
        mock_fdb.connect.return_value = mock_conn
        mock_fdb.isc_info_ods_version = 14

        url = reverse("core:settings_conexao_test")
        with patch.dict("sys.modules", {"fdb": mock_fdb}):
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
        assert "Autenticação OK" in data["message"]

    @patch("socket.create_connection")
    def test_firebird_auth_failure(self, mock_sock, admin_client):
        mock_sock.return_value.close.return_value = None

        mock_fdb = MagicMock()
        mock_fdb.connect.side_effect = Exception("auth failed")
        mock_fdb.isc_info_ods_version = 14

        url = reverse("core:settings_conexao_test")
        with patch.dict("sys.modules", {"fdb": mock_fdb}):
            response = admin_client.post(
                url,
                {
                    "sistema": "RI",
                    "tipo_conexao": "FIREBIRD",
                    "host": "10.0.0.1",
                    "porta": "3050",
                    "database": "/opt/firebird/test.fdb",
                    "usuario": "SYSDBA",
                    "senha": "wrong",
                },
            )
        data = response.json()
        assert data["status"] == "error"
        assert "autenticação" in data["message"].lower()

    @patch("socket.create_connection")
    def test_mssql_auth_success(self, mock_sock, admin_client):
        mock_sock.return_value.close.return_value = None

        mock_pymssql = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ["Microsoft SQL Server 2022"]
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value = mock_cursor
        mock_pymssql.connect.return_value = mock_conn

        url = reverse("core:settings_conexao_test")
        with patch.dict("sys.modules", {"pymssql": mock_pymssql}):
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
        assert "Autenticação OK" in data["message"]

    @patch("socket.create_connection")
    def test_mssql_auth_failure(self, mock_sock, admin_client):
        mock_sock.return_value.close.return_value = None

        mock_pymssql = MagicMock()
        mock_pymssql.connect.side_effect = Exception("Login failed for user 'sa'")

        url = reverse("core:settings_conexao_test")
        with patch.dict("sys.modules", {"pymssql": mock_pymssql}):
            response = admin_client.post(
                url,
                {
                    "sistema": "RI",
                    "tipo_conexao": "MSSQL",
                    "host": "10.0.0.1",
                    "porta": "1433",
                    "database": "test",
                    "usuario": "sa",
                    "senha": "wrong",
                },
            )
        data = response.json()
        assert data["status"] == "error"
        assert "autenticação" in data["message"].lower()
