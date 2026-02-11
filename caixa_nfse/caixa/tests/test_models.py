"""
Unit tests for caixa models.
"""

from decimal import Decimal

import pytest

from caixa_nfse.caixa.models import (
    AberturaCaixa,
    Caixa,
    FechamentoCaixa,
    MovimentoCaixa,
    StatusCaixa,
    StatusFechamento,
    TipoMovimento,
)


@pytest.mark.django_db
class TestCaixaModel:
    """Tests for Caixa model."""

    def test_create_caixa(self, tenant):
        """Should create a cash register with valid data."""
        caixa = Caixa.objects.create(
            tenant=tenant,
            identificador="CAIXA-01",
            tipo="FISICO",
        )
        assert caixa.id is not None
        assert caixa.identificador == "CAIXA-01"
        assert caixa.ativo is True

    def test_caixa_str(self, caixa):
        """Should return identificador and status as string representation."""
        assert "CAIXA-01" in str(caixa)

    def test_caixa_status_inicial(self, caixa):
        """New caixa should have FECHADO status."""
        assert caixa.status == StatusCaixa.FECHADO

    def test_caixa_esta_aberto_false(self, caixa):
        """Caixa without abertura should not be open."""
        assert caixa.esta_aberto is False

    def test_caixa_unique_identificador_per_tenant(self, tenant):
        """Should not allow duplicate identificador for same tenant."""
        from django.db import IntegrityError

        Caixa.objects.create(tenant=tenant, identificador="CAIXA-01", tipo="FISICO")
        with pytest.raises(IntegrityError):
            Caixa.objects.create(tenant=tenant, identificador="CAIXA-01", tipo="FISICO")


@pytest.mark.django_db
class TestAberturaCaixaModel:
    """Tests for AberturaCaixa model."""

    def test_create_abertura(self, caixa, user):
        """Should create an abertura with valid data."""
        # Ensure user has same tenant as caixa
        user.tenant = caixa.tenant
        user.save()

        abertura = AberturaCaixa.objects.create(
            tenant=caixa.tenant,
            caixa=caixa,
            operador=user,
            saldo_abertura=Decimal("100.00"),
            fundo_troco=Decimal("50.00"),
        )
        assert abertura.id is not None
        assert abertura.hash_registro is not None

    def test_saldo_movimentos_sem_movimentos(self, abertura):
        """Saldo should equal saldo_abertura without movements."""
        # saldo_movimentos includes saldo_abertura
        assert abertura.saldo_movimentos == Decimal("100.00")

    def test_saldo_movimentos_com_entrada(self, abertura, forma_pagamento):
        """Should calculate saldo with entrada."""
        MovimentoCaixa.objects.create(
            tenant=abertura.tenant,
            abertura=abertura,
            tipo=TipoMovimento.ENTRADA,
            forma_pagamento=forma_pagamento,
            valor=Decimal("150.00"),
        )
        # saldo_abertura (100) + entrada (150) = 250
        assert abertura.saldo_movimentos == Decimal("250.00")

    def test_saldo_movimentos_com_saida(self, abertura, forma_pagamento):
        """Should calculate saldo with saida."""
        MovimentoCaixa.objects.create(
            tenant=abertura.tenant,
            abertura=abertura,
            tipo=TipoMovimento.SAIDA,
            forma_pagamento=forma_pagamento,
            valor=Decimal("30.00"),
        )
        # saldo_abertura (100) - saida (30) = 70
        assert abertura.saldo_movimentos == Decimal("70.00")

    def test_total_entradas(self, abertura, forma_pagamento):
        """Should calculate total entradas."""
        MovimentoCaixa.objects.create(
            tenant=abertura.tenant,
            abertura=abertura,
            tipo=TipoMovimento.ENTRADA,
            forma_pagamento=forma_pagamento,
            valor=Decimal("100.00"),
        )
        MovimentoCaixa.objects.create(
            tenant=abertura.tenant,
            abertura=abertura,
            tipo=TipoMovimento.ENTRADA,
            forma_pagamento=forma_pagamento,
            valor=Decimal("50.00"),
        )
        assert abertura.total_entradas == Decimal("150.00")

    def test_total_saidas(self, abertura, forma_pagamento):
        """Should calculate total saidas."""
        MovimentoCaixa.objects.create(
            tenant=abertura.tenant,
            abertura=abertura,
            tipo=TipoMovimento.SAIDA,
            forma_pagamento=forma_pagamento,
            valor=Decimal("25.00"),
        )
        assert abertura.total_saidas == Decimal("25.00")

    def test_is_operacional_hoje(self, abertura):
        """Abertura created today should be operacional."""
        from unittest.mock import patch

        with patch("caixa_nfse.caixa.models.timezone") as mock_tz:
            mock_tz.localdate.return_value = abertura.data_hora.date()
            assert abertura.is_operacional_hoje is True


@pytest.mark.django_db
class TestMovimentoCaixaModel:
    """Tests for MovimentoCaixa model."""

    def test_create_movimento(self, abertura, forma_pagamento):
        """Should create a movimento with valid data."""
        movimento = MovimentoCaixa.objects.create(
            tenant=abertura.tenant,
            abertura=abertura,
            tipo=TipoMovimento.ENTRADA,
            forma_pagamento=forma_pagamento,
            valor=Decimal("100.00"),
        )
        assert movimento.id is not None
        assert movimento.hash_registro is not None

    def test_movimento_is_entrada(self, abertura, forma_pagamento):
        """Should identify entrada movement."""
        movimento = MovimentoCaixa.objects.create(
            tenant=abertura.tenant,
            abertura=abertura,
            tipo=TipoMovimento.ENTRADA,
            forma_pagamento=forma_pagamento,
            valor=Decimal("100.00"),
        )
        assert movimento.is_entrada is True
        assert movimento.is_saida is False

    def test_movimento_is_saida(self, abertura, forma_pagamento):
        """Should identify saida movement."""
        movimento = MovimentoCaixa.objects.create(
            tenant=abertura.tenant,
            abertura=abertura,
            tipo=TipoMovimento.SAIDA,
            forma_pagamento=forma_pagamento,
            valor=Decimal("50.00"),
        )
        assert movimento.is_entrada is False
        assert movimento.is_saida is True

    def test_movimento_sangria_is_saida(self, abertura, forma_pagamento):
        """Sangria should be considered saida."""
        movimento = MovimentoCaixa.objects.create(
            tenant=abertura.tenant,
            abertura=abertura,
            tipo=TipoMovimento.SANGRIA,
            forma_pagamento=forma_pagamento,
            valor=Decimal("200.00"),
        )
        assert movimento.is_saida is True

    def test_movimento_suprimento_is_entrada(self, abertura, forma_pagamento):
        """Suprimento should be considered entrada."""
        movimento = MovimentoCaixa.objects.create(
            tenant=abertura.tenant,
            abertura=abertura,
            tipo=TipoMovimento.SUPRIMENTO,
            forma_pagamento=forma_pagamento,
            valor=Decimal("300.00"),
        )
        assert movimento.is_entrada is True


@pytest.mark.django_db
class TestFechamentoCaixaModel:
    """Tests for FechamentoCaixa model."""

    def test_create_fechamento(self, abertura):
        """Should create fechamento with valid data."""
        fechamento = FechamentoCaixa.objects.create(
            tenant=abertura.tenant,
            abertura=abertura,
            operador=abertura.operador,
            saldo_sistema=Decimal("150.00"),
            saldo_informado=Decimal("150.00"),
        )
        assert fechamento.id is not None
        assert fechamento.hash_registro is not None

    def test_fechamento_diferenca_zero(self, abertura):
        """Should have zero diferenca when saldos match."""
        fechamento = FechamentoCaixa.objects.create(
            tenant=abertura.tenant,
            abertura=abertura,
            operador=abertura.operador,
            saldo_sistema=Decimal("100.00"),
            saldo_informado=Decimal("100.00"),
        )
        assert fechamento.diferenca == Decimal("0.00")

    def test_fechamento_diferenca_positiva(self, abertura):
        """Should calculate positive diferenca (sobra)."""
        fechamento = FechamentoCaixa.objects.create(
            tenant=abertura.tenant,
            abertura=abertura,
            operador=abertura.operador,
            saldo_sistema=Decimal("100.00"),
            saldo_informado=Decimal("110.00"),
        )
        assert fechamento.diferenca == Decimal("10.00")

    def test_fechamento_diferenca_negativa(self, abertura):
        """Should calculate negative diferenca (falta)."""
        fechamento = FechamentoCaixa.objects.create(
            tenant=abertura.tenant,
            abertura=abertura,
            operador=abertura.operador,
            saldo_sistema=Decimal("100.00"),
            saldo_informado=Decimal("95.00"),
        )
        assert fechamento.diferenca == Decimal("-5.00")

    def test_fechamento_status_inicial(self, abertura):
        """New fechamento should have PENDENTE status."""
        fechamento = FechamentoCaixa.objects.create(
            tenant=abertura.tenant,
            abertura=abertura,
            operador=abertura.operador,
            saldo_sistema=Decimal("100.00"),
            saldo_informado=Decimal("100.00"),
        )
        assert fechamento.status == StatusFechamento.PENDENTE
