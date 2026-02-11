"""
Tests for caixa/tables.py: render_valor, render_emolumento, render_valor_total_taxas.
Covers lines 66-68, 77-79, 83-85.
"""

from decimal import Decimal
from unittest.mock import MagicMock

from caixa_nfse.caixa.tables import MovimentoTable


class TestMovimentoTableRenders:
    def _make_record(self, is_entrada=True):
        record = MagicMock()
        record.is_entrada = is_entrada
        return record

    def test_render_valor_entrada(self):
        table = MovimentoTable([])
        record = self._make_record(is_entrada=True)
        result = table.render_valor(Decimal("100.00"), record)
        assert "text-success" in str(result)
        assert "+" in str(result)
        assert "100" in str(result)

    def test_render_valor_saida(self):
        table = MovimentoTable([])
        record = self._make_record(is_entrada=False)
        result = table.render_valor(Decimal("50.00"), record)
        assert "text-danger" in str(result)
        assert "-" in str(result)

    def test_render_emolumento_with_value(self):
        table = MovimentoTable([])
        result = table.render_emolumento(Decimal("25.50"))
        assert "R$" in result
        assert "25" in result

    def test_render_emolumento_zero(self):
        table = MovimentoTable([])
        result = table.render_emolumento(Decimal("0.00"))
        assert result == "—"

    def test_render_emolumento_none(self):
        table = MovimentoTable([])
        result = table.render_emolumento(None)
        assert result == "—"

    def test_render_valor_total_taxas_with_value(self):
        table = MovimentoTable([])
        result = table.render_valor_total_taxas(Decimal("150.00"))
        assert "R$" in result
        assert "150" in result

    def test_render_valor_total_taxas_zero(self):
        table = MovimentoTable([])
        result = table.render_valor_total_taxas(Decimal("0.00"))
        assert result == "—"

    def test_render_valor_total_taxas_none(self):
        table = MovimentoTable([])
        result = table.render_valor_total_taxas(None)
        assert result == "—"
