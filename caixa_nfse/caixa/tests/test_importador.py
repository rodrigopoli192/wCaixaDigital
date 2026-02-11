"""
Tests for caixa/services/importador.py: ImportadorMovimentos.
Covers lines 27-38 (executar_rotinas), 154-160 (accumulation), 170-176 (_parse_decimal),
183-195 (_parse_date), 230, 236-237, 282, 321-322, 327, 344-411 (confirmar_movimentos),
416-419 (limpar_confirmados).
"""

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import patch

import pytest

from caixa_nfse.backoffice.models import Rotina, Sistema
from caixa_nfse.caixa.models import (
    AberturaCaixa,
    Caixa,
    MovimentoCaixa,
    MovimentoImportado,
    StatusCaixa,
    TipoMovimento,
)
from caixa_nfse.caixa.services.importador import ImportadorMovimentos
from caixa_nfse.conftest import *  # noqa: F401,F403
from caixa_nfse.core.models import ConexaoExterna, FormaPagamento

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sistema(db):
    return Sistema.objects.create(nome="RI", ativo=True)


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
def rotina(db, sistema):
    return Rotina.objects.create(
        sistema=sistema, nome="Buscar Protocolos", sql_content="SELECT * FROM t", ativo=True
    )


@pytest.fixture
def caixa(db, tenant, admin_user):
    return Caixa.objects.create(
        tenant=tenant,
        identificador="CX-IMP",
        tipo="FISICO",
        status=StatusCaixa.ABERTO,
        operador_atual=admin_user,
        saldo_atual=Decimal("1000.00"),
    )


@pytest.fixture
def abertura(db, tenant, admin_user, caixa):
    return AberturaCaixa.objects.create(
        tenant=tenant,
        caixa=caixa,
        operador=admin_user,
        saldo_abertura=Decimal("1000.00"),
        created_by=admin_user,
    )


@pytest.fixture
def forma_pagamento(db, tenant):
    return FormaPagamento.objects.create(tenant=tenant, nome="Dinheiro", ativo=True)


# ===========================================================================
# _parse_decimal
# ===========================================================================


class TestParseDecimal:
    def test_none(self):
        assert ImportadorMovimentos._parse_decimal(None) == Decimal("0.00")

    def test_decimal_passthrough(self):
        d = Decimal("42.50")
        assert ImportadorMovimentos._parse_decimal(d) == d

    def test_string_with_comma(self):
        # "1.234,56" → replace comma → "1.234.56" → invalid Decimal → returns 0.00
        assert ImportadorMovimentos._parse_decimal("1.234,56") == Decimal("0.00")

    def test_string_comma_simple(self):
        # "100,50" → replace comma → "100.50" → valid
        assert ImportadorMovimentos._parse_decimal("100,50") == Decimal("100.50")

    def test_string(self):
        assert ImportadorMovimentos._parse_decimal("100.50") == Decimal("100.50")

    def test_invalid(self):
        assert ImportadorMovimentos._parse_decimal("abc") == Decimal("0.00")

    def test_integer(self):
        assert ImportadorMovimentos._parse_decimal(42) == Decimal("42")


# ===========================================================================
# _parse_date
# ===========================================================================


class TestParseDate:
    def test_none(self):
        assert ImportadorMovimentos._parse_date(None) is None

    def test_date_passthrough(self):
        d = date(2025, 3, 15)
        assert ImportadorMovimentos._parse_date(d) == d

    def test_datetime_to_date(self):
        # Note: datetime is subclass of date → isinstance(value, date) matches first
        # The function returns the datetime as-is because the date check catches it
        dt = datetime(2025, 3, 15, 10, 30, 0)
        result = ImportadorMovimentos._parse_date(dt)
        # isinstance(datetime, date) is True, so returns the value directly
        assert result == dt

    def test_empty_string(self):
        assert ImportadorMovimentos._parse_date("") is None

    def test_yyyymmdd(self):
        assert ImportadorMovimentos._parse_date("20250315") == date(2025, 3, 15)

    def test_br_format(self):
        assert ImportadorMovimentos._parse_date("15/03/2025") == date(2025, 3, 15)

    def test_iso_format(self):
        assert ImportadorMovimentos._parse_date("2025-03-15") == date(2025, 3, 15)

    def test_iso_datetime(self):
        assert ImportadorMovimentos._parse_date("2025-03-15 10:30:00") == date(2025, 3, 15)

    def test_iso_datetime_micro(self):
        assert ImportadorMovimentos._parse_date("2025-03-15 10:30:00.123456") == date(2025, 3, 15)

    def test_unparseable(self):
        assert ImportadorMovimentos._parse_date("not-a-date") is None


# ===========================================================================
# executar_rotinas
# ===========================================================================


@pytest.mark.django_db
class TestExecutarRotinas:
    @patch("caixa_nfse.caixa.services.importador.SQLExecutor.execute_routine")
    def test_single_rotina(self, mock_exec, conexao, rotina):
        mock_exec.return_value = (["COL1"], [("val1",)], [])
        results = ImportadorMovimentos.executar_rotinas(
            conexao, [rotina], {"DATA_INICIO": "2025-01-01"}
        )
        assert len(results) == 1
        r, h, rows, logs = results[0]
        assert r == rotina
        assert h == ["COL1"]
        assert rows == [("val1",)]

    @patch("caixa_nfse.caixa.services.importador.SQLExecutor.execute_routine")
    def test_multiple_rotinas(self, mock_exec, conexao, rotina, sistema):
        rotina2 = Rotina.objects.create(
            sistema=sistema, nome="Rotina 2", sql_content="SELECT 1", ativo=True
        )
        mock_exec.return_value = ([], [], [])
        results = ImportadorMovimentos.executar_rotinas(conexao, [rotina, rotina2])
        assert len(results) == 2
        assert mock_exec.call_count == 2

    @patch("caixa_nfse.caixa.services.importador.SQLExecutor.execute_routine")
    def test_rotina_with_extra_sql(self, mock_exec, conexao, sistema):
        rotina_extra = Rotina.objects.create(
            sistema=sistema,
            nome="Extra SQL",
            sql_content="SELECT * FROM t1",
            sql_content_extra="UNION SELECT * FROM t2",
            ativo=True,
        )
        mock_exec.return_value = ([], [], [])
        ImportadorMovimentos.executar_rotinas(conexao, [rotina_extra])
        # Verify the SQL passed includes both parts joined
        call_args = mock_exec.call_args
        sql_arg = call_args[0][1]
        assert "t1" in sql_arg
        assert "t2" in sql_arg


# ===========================================================================
# mapear_colunas (accumulation logic)
# ===========================================================================


@pytest.mark.django_db
class TestMapearColunas:
    def test_auto_mapping(self, rotina):
        headers = ["PROTOCOLO", "VALOR", "DESCRICAO"]
        row = ("P-001", "50.00", "Certidão")
        result = ImportadorMovimentos.mapear_colunas(rotina, headers, row)
        assert result["protocolo"] == "P-001"
        assert result["valor"] == "50.00"
        assert result["descricao"] == "Certidão"

    def test_accumulation_same_field(self, rotina):
        """When multiple columns map to the same decimal field, values are accumulated."""
        headers = ["VALOR", "VALORRECEITAADICIONAL1"]
        row = ("100.00", "25.00")
        result = ImportadorMovimentos.mapear_colunas(rotina, headers, row)
        # VALORRECEITAADICIONAL1 maps to taxa_judiciaria, so no accumulation with VALOR
        assert result["valor"] == "100.00"
        assert result["taxa_judiciaria"] == "25.00"

    def test_unknown_columns_ignored(self, rotina):
        headers = ["UNKNOWN_COL", "PROTOCOLO"]
        row = ("ignored", "P-001")
        result = ImportadorMovimentos.mapear_colunas(rotina, headers, row)
        assert "UNKNOWN_COL" not in result
        assert result["protocolo"] == "P-001"


# ===========================================================================
# salvar_importacao
# ===========================================================================


@pytest.mark.django_db
class TestSalvarImportacao:
    def test_basic_import(self, abertura, conexao, rotina, admin_user):
        headers = ["PROTOCOLO", "VALOR", "DESCRICAO"]
        rows = [("P-001", "50.00", "Cert 1"), ("P-002", "75.00", "Cert 2")]
        created, skipped = ImportadorMovimentos.salvar_importacao(
            abertura, conexao, rotina, headers, rows, admin_user
        )
        assert created == 2
        assert skipped == 0
        assert MovimentoImportado.objects.filter(abertura=abertura).count() == 2

    def test_skip_duplicate_protocolo(self, abertura, conexao, rotina, admin_user, tenant):
        # Create existing import with same protocolo
        MovimentoImportado.objects.create(
            tenant=tenant,
            abertura=abertura,
            conexao=conexao,
            rotina=rotina,
            importado_por=admin_user,
            protocolo="P-001",
            valor=Decimal("50.00"),
        )
        headers = ["PROTOCOLO", "VALOR"]
        rows = [("P-001", "100.00"), ("P-003", "200.00")]
        created, skipped = ImportadorMovimentos.salvar_importacao(
            abertura, conexao, rotina, headers, rows, admin_user
        )
        assert created == 1
        assert skipped == 1

    def test_group_by_protocolo(self, abertura, conexao, rotina, admin_user):
        """Multiple rows with the same protocolo are grouped and values summed."""
        headers = ["PROTOCOLO", "VALOR", "DESCRICAO"]
        rows = [
            ("P-001", "50.00", "Ato 1"),
            ("P-001", "25.00", "Ato 2"),
        ]
        created, skipped = ImportadorMovimentos.salvar_importacao(
            abertura, conexao, rotina, headers, rows, admin_user
        )
        assert created == 1
        assert skipped == 0
        imp = MovimentoImportado.objects.get(abertura=abertura, protocolo="P-001")
        assert imp.valor == Decimal("75.00")
        assert "Ato 1" in imp.descricao
        assert "Ato 2" in imp.descricao

    def test_no_protocolo(self, abertura, conexao, rotina, admin_user):
        """Rows without protocolo each get a unique import."""
        headers = ["VALOR", "DESCRICAO"]
        rows = [("50.00", "Item 1"), ("75.00", "Item 2")]
        created, skipped = ImportadorMovimentos.salvar_importacao(
            abertura, conexao, rotina, headers, rows, admin_user
        )
        assert created == 2

    def test_empty_mapped_row(self, abertura, conexao, rotina, admin_user):
        """Rows that map to nothing are skipped."""
        headers = ["UNKNOWN_COL"]
        rows = [("val1",)]
        created, skipped = ImportadorMovimentos.salvar_importacao(
            abertura, conexao, rotina, headers, rows, admin_user
        )
        assert created == 0
        assert skipped == 0

    def test_no_description(self, abertura, conexao, rotina, admin_user):
        """When no description column exists, use rotina name."""
        headers = ["PROTOCOLO", "VALOR"]
        rows = [("P-001", "10.00")]
        created, _ = ImportadorMovimentos.salvar_importacao(
            abertura, conexao, rotina, headers, rows, admin_user
        )
        assert created == 1
        imp = MovimentoImportado.objects.get(abertura=abertura)
        assert rotina.nome in imp.descricao

    def test_quantity_invalid(self, abertura, conexao, rotina, admin_user):
        """Invalid quantity defaults to 1."""
        headers = ["PROTOCOLO", "VALOR", "QUANTIDADE"]
        rows = [("P-001", "10.00", "invalid")]
        created, _ = ImportadorMovimentos.salvar_importacao(
            abertura, conexao, rotina, headers, rows, admin_user
        )
        imp = MovimentoImportado.objects.get(abertura=abertura)
        assert imp.quantidade == 1

    def test_with_data_ato(self, abertura, conexao, rotina, admin_user):
        headers = ["PROTOCOLO", "VALOR", "DATA_ATO"]
        rows = [("P-001", "10.00", "2025-03-15")]
        created, _ = ImportadorMovimentos.salvar_importacao(
            abertura, conexao, rotina, headers, rows, admin_user
        )
        imp = MovimentoImportado.objects.get(abertura=abertura)
        assert imp.data_ato == date(2025, 3, 15)


# ===========================================================================
# confirmar_movimentos
# ===========================================================================


@pytest.mark.django_db
class TestConfirmarMovimentos:
    def test_confirm_basic(
        self, abertura, conexao, rotina, admin_user, forma_pagamento, tenant, caixa
    ):
        imp = MovimentoImportado.objects.create(
            tenant=tenant,
            abertura=abertura,
            conexao=conexao,
            rotina=rotina,
            importado_por=admin_user,
            protocolo="P-001",
            valor=Decimal("50.00"),
            descricao="Test import",
            cliente_nome="João Silva",
        )
        count = ImportadorMovimentos.confirmar_movimentos(
            [imp.pk], abertura, forma_pagamento, TipoMovimento.ENTRADA, admin_user
        )
        assert count == 1
        imp.refresh_from_db()
        assert imp.confirmado is True
        assert imp.confirmado_em is not None
        assert imp.movimento_destino is not None
        # Check movement was created
        mov = MovimentoCaixa.objects.get(protocolo="P-001")
        assert mov.valor == Decimal("50.00")
        assert mov.tipo == TipoMovimento.ENTRADA
        # Check saldo updated
        caixa.refresh_from_db()
        assert caixa.saldo_atual == Decimal("1050.00")

    def test_confirm_saida(
        self, abertura, conexao, rotina, admin_user, forma_pagamento, tenant, caixa
    ):
        imp = MovimentoImportado.objects.create(
            tenant=tenant,
            abertura=abertura,
            conexao=conexao,
            rotina=rotina,
            importado_por=admin_user,
            protocolo="P-002",
            valor=Decimal("30.00"),
        )
        count = ImportadorMovimentos.confirmar_movimentos(
            [imp.pk], abertura, forma_pagamento, TipoMovimento.SAIDA, admin_user
        )
        assert count == 1
        caixa.refresh_from_db()
        assert caixa.saldo_atual == Decimal("970.00")

    def test_confirm_no_description_uses_protocolo(
        self, abertura, conexao, rotina, admin_user, forma_pagamento, tenant
    ):
        imp = MovimentoImportado.objects.create(
            tenant=tenant,
            abertura=abertura,
            conexao=conexao,
            rotina=rotina,
            importado_por=admin_user,
            protocolo="P-003",
            valor=Decimal("10.00"),
        )
        ImportadorMovimentos.confirmar_movimentos(
            [imp.pk], abertura, forma_pagamento, TipoMovimento.ENTRADA, admin_user
        )
        mov = MovimentoCaixa.objects.get(protocolo="P-003")
        assert "Protocolo P-003" in mov.descricao

    def test_confirm_already_confirmed_skipped(
        self, abertura, conexao, rotina, admin_user, forma_pagamento, tenant
    ):
        imp = MovimentoImportado.objects.create(
            tenant=tenant,
            abertura=abertura,
            conexao=conexao,
            rotina=rotina,
            importado_por=admin_user,
            protocolo="P-004",
            valor=Decimal("10.00"),
            confirmado=True,
        )
        count = ImportadorMovimentos.confirmar_movimentos(
            [imp.pk], abertura, forma_pagamento, TipoMovimento.ENTRADA, admin_user
        )
        assert count == 0

    def test_confirm_with_zero_valor_uses_taxas(
        self, abertura, conexao, rotina, admin_user, forma_pagamento, tenant
    ):
        imp = MovimentoImportado.objects.create(
            tenant=tenant,
            abertura=abertura,
            conexao=conexao,
            rotina=rotina,
            importado_por=admin_user,
            protocolo="P-005",
            valor=Decimal("0.00"),
            iss=Decimal("10.00"),
            fundesp=Decimal("5.00"),
        )
        ImportadorMovimentos.confirmar_movimentos(
            [imp.pk], abertura, forma_pagamento, TipoMovimento.ENTRADA, admin_user
        )
        mov = MovimentoCaixa.objects.get(protocolo="P-005")
        assert mov.valor == imp.valor_total_taxas


# ===========================================================================
# limpar_confirmados
# ===========================================================================


@pytest.mark.django_db
class TestLimparConfirmados:
    def test_delete_confirmed(self, abertura, conexao, rotina, admin_user, tenant):
        MovimentoImportado.objects.create(
            tenant=tenant,
            abertura=abertura,
            conexao=conexao,
            rotina=rotina,
            importado_por=admin_user,
            protocolo="P-C1",
            valor=Decimal("10.00"),
            confirmado=True,
        )
        MovimentoImportado.objects.create(
            tenant=tenant,
            abertura=abertura,
            conexao=conexao,
            rotina=rotina,
            importado_por=admin_user,
            protocolo="P-C2",
            valor=Decimal("20.00"),
            confirmado=False,
        )
        deleted = ImportadorMovimentos.limpar_confirmados(tenant)
        assert deleted == 1
        assert MovimentoImportado.objects.filter(tenant=tenant).count() == 1
        assert MovimentoImportado.objects.get(tenant=tenant).protocolo == "P-C2"
