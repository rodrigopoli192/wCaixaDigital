"""
Tests for core/services/sql_executor.py: SQLExecutor.
Covers lines 25-48 (get_connection), 56-152 (execute_routine).
"""

from unittest.mock import MagicMock, patch

import pytest

from caixa_nfse.conftest import *  # noqa: F401,F403
from caixa_nfse.core.models import ConexaoExterna
from caixa_nfse.core.services.sql_executor import SQLExecutor

# ---------------------------------------------------------------------------
# extract_variables
# ---------------------------------------------------------------------------


class TestExtractVariables:
    def test_basic(self):
        sql = "SELECT * FROM t WHERE date >= @DATA_INICIO AND date <= @DATA_FIM"
        result = SQLExecutor.extract_variables(sql)
        assert set(result) == {"DATA_INICIO", "DATA_FIM"}

    def test_no_variables(self):
        assert SQLExecutor.extract_variables("SELECT 1") == []

    def test_duplicates(self):
        sql = "SELECT @A, @A"
        assert SQLExecutor.extract_variables(sql) == ["A"]


# ---------------------------------------------------------------------------
# get_connection
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestGetConnection:
    def test_firebird_connection(self, tenant):
        from caixa_nfse.backoffice.models import Sistema

        sistema = Sistema.objects.create(nome="Test", ativo=True)
        conexao = ConexaoExterna.objects.create(
            tenant=tenant,
            sistema=sistema,
            tipo_conexao="FIREBIRD",
            host="10.0.0.1",
            porta=3050,
            database="/opt/data.fdb",
            usuario="SYSDBA",
            senha="masterkey",
        )
        with patch("caixa_nfse.core.services.sql_executor.fdb") as mock_fdb:
            mock_fdb.connect.return_value = MagicMock()
            conn = SQLExecutor.get_connection(conexao)
            mock_fdb.connect.assert_called_once()
            assert conn is not None

    def test_mssql_connection(self, tenant):
        from caixa_nfse.backoffice.models import Sistema

        sistema = Sistema.objects.create(nome="Test", ativo=True)
        conexao = ConexaoExterna.objects.create(
            tenant=tenant,
            sistema=sistema,
            tipo_conexao="MSSQL",
            host="10.0.0.1",
            porta=1433,
            database="testdb",
            usuario="sa",
            senha="pass",
        )
        with patch("caixa_nfse.core.services.sql_executor.pymssql") as mock_pymssql:
            mock_pymssql.connect.return_value = MagicMock()
            conn = SQLExecutor.get_connection(conexao)
            mock_pymssql.connect.assert_called_once()
            assert conn is not None

    def test_unsupported_type(self, tenant):
        from caixa_nfse.backoffice.models import Sistema

        sistema = Sistema.objects.create(nome="Test", ativo=True)
        conexao = ConexaoExterna.objects.create(
            tenant=tenant,
            sistema=sistema,
            tipo_conexao="POSTGRES",
            host="10.0.0.1",
            porta=5432,
            database="testdb",
            usuario="pg",
            senha="pass",
        )
        with pytest.raises(ValueError, match="não suportado"):
            SQLExecutor.get_connection(conexao)


# ---------------------------------------------------------------------------
# execute_routine
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestExecuteRoutine:
    @pytest.fixture
    def conexao(self, tenant):
        from caixa_nfse.backoffice.models import Sistema

        sistema = Sistema.objects.create(nome="Test", ativo=True)
        return ConexaoExterna.objects.create(
            tenant=tenant,
            sistema=sistema,
            tipo_conexao="MSSQL",
            host="10.0.0.1",
            porta=1433,
            database="testdb",
            usuario="sa",
            senha="pass",
        )

    @patch("caixa_nfse.core.services.sql_executor.SQLExecutor.get_connection")
    def test_success_with_results(self, mock_get_conn, conexao):
        mock_cursor = MagicMock()
        mock_cursor.description = [("PROTOCOLO",), ("VALOR",)]
        mock_cursor.fetchall.return_value = [("P-001", 100.0), ("P-002", 200.0)]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        headers, rows, logs = SQLExecutor.execute_routine(
            conexao, "SELECT * FROM t WHERE dt >= @DATA_INICIO", {"DATA_INICIO": "2025-01-01"}
        )
        assert headers == ["PROTOCOLO", "VALOR"]
        assert len(rows) == 2
        assert any("registros retornados" in l["msg"] for l in logs)
        mock_conn.close.assert_called_once()

    @patch("caixa_nfse.core.services.sql_executor.SQLExecutor.get_connection")
    def test_success_no_results(self, mock_get_conn, conexao):
        mock_cursor = MagicMock()
        mock_cursor.description = None
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        headers, rows, logs = SQLExecutor.execute_routine(conexao, "UPDATE t SET x=1")
        assert headers == []
        assert rows == []
        assert any("Nenhum resultado" in l["msg"] for l in logs)

    @patch("caixa_nfse.core.services.sql_executor.SQLExecutor.get_connection")
    def test_connection_error(self, mock_get_conn, conexao):
        mock_get_conn.side_effect = Exception("Connection refused")
        headers, rows, logs = SQLExecutor.execute_routine(conexao, "SELECT 1")
        assert headers == []
        assert rows == []
        assert any("Erro na execução" in l["msg"] for l in logs)

    def test_invalid_variable_name(self, conexao):
        headers, rows, logs = SQLExecutor.execute_routine(
            conexao, "SELECT @SAFE", {"DROP TABLE--": "hacked"}
        )
        assert headers == []
        assert rows == []
        assert any("inválido" in l["msg"] for l in logs)

    @patch("caixa_nfse.core.services.sql_executor.SQLExecutor.get_connection")
    def test_date_format_br(self, mock_get_conn, conexao):
        mock_cursor = MagicMock()
        mock_cursor.description = [("X",)]
        mock_cursor.fetchall.return_value = [("ok",)]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        headers, rows, logs = SQLExecutor.execute_routine(
            conexao, "SELECT * FROM t WHERE dt = @DATA", {"DATA": "15/03/2025"}
        )
        assert headers == ["X"]
        assert any("20250315" in l["msg"] for l in logs)

    @patch("caixa_nfse.core.services.sql_executor.SQLExecutor.get_connection")
    def test_long_sql_truncated_in_log(self, mock_get_conn, conexao):
        mock_cursor = MagicMock()
        mock_cursor.description = [("X",)]
        mock_cursor.fetchall.return_value = [("ok",)]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        long_sql = "SELECT " + "A" * 250 + " FROM t"
        headers, rows, logs = SQLExecutor.execute_routine(conexao, long_sql)
        assert headers == ["X"]
        assert any("..." in l["msg"] for l in logs)

    @patch("caixa_nfse.core.services.sql_executor.SQLExecutor.get_connection")
    def test_no_params(self, mock_get_conn, conexao):
        mock_cursor = MagicMock()
        mock_cursor.description = [("ID",)]
        mock_cursor.fetchall.return_value = [(1,)]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        headers, rows, logs = SQLExecutor.execute_routine(conexao, "SELECT 1 AS ID")
        assert headers == ["ID"]
        assert rows == [(1,)]
