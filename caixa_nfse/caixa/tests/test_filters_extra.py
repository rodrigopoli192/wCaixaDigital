"""
Tests for MovimentoFilter.filter_busca.
Covers missing lines from caixa/filters.py.
"""

from decimal import Decimal

import pytest

from caixa_nfse.caixa.filters import MovimentoFilter
from caixa_nfse.caixa.models import AberturaCaixa, Caixa, MovimentoCaixa, TipoMovimento
from caixa_nfse.core.models import FormaPagamento
from caixa_nfse.tests.factories import TenantFactory, UserFactory


@pytest.mark.django_db
class TestMovimentoFilter:
    def setup_method(self):
        self.tenant = TenantFactory()
        self.user = UserFactory(tenant=self.tenant, pode_operar_caixa=True)
        self.forma = FormaPagamento.objects.create(
            tenant=self.tenant,
            nome="Dinheiro",
            ativo=True,
        )
        self.caixa = Caixa.objects.create(
            tenant=self.tenant,
            identificador="CX-FILTER",
            saldo_atual=Decimal("0"),
        )
        self.abertura = AberturaCaixa.objects.create(
            caixa=self.caixa,
            operador=self.user,
            saldo_abertura=Decimal("0"),
            tenant=self.tenant,
        )
        self.mov = MovimentoCaixa.objects.create(
            abertura=self.abertura,
            tenant=self.tenant,
            tipo=TipoMovimento.ENTRADA,
            valor=Decimal("50.00"),
            descricao="Pagamento cliente X",
            protocolo="PROTO-123",
            forma_pagamento=self.forma,
        )

    def test_filter_busca_by_protocolo(self):
        qs = MovimentoCaixa.objects.filter(tenant=self.tenant)
        f = MovimentoFilter(data={"busca": "PROTO"}, queryset=qs)
        assert f.qs.count() == 1

    def test_filter_busca_by_descricao(self):
        qs = MovimentoCaixa.objects.filter(tenant=self.tenant)
        f = MovimentoFilter(data={"busca": "cliente X"}, queryset=qs)
        assert f.qs.count() == 1

    def test_filter_busca_empty(self):
        qs = MovimentoCaixa.objects.filter(tenant=self.tenant)
        f = MovimentoFilter(data={"busca": ""}, queryset=qs)
        assert f.qs.count() == 1  # No filtering

    def test_filter_busca_no_match(self):
        qs = MovimentoCaixa.objects.filter(tenant=self.tenant)
        f = MovimentoFilter(data={"busca": "INEXISTENTE"}, queryset=qs)
        assert f.qs.count() == 0
