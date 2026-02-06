import pytest
from django.db import IntegrityError

from caixa_nfse.tests.factories import (
    CentroCustoFactory,
    LancamentoContabilFactory,
    PartidaLancamentoFactory,
    PlanoContasFactory,
    TenantFactory,
)


@pytest.mark.django_db
class TestPlanoContas:
    """Tests for PlanoContas model."""

    def test_create_plano_contas(self):
        """Should create a PlanoContas instance."""
        conta = PlanoContasFactory()
        assert conta.pk is not None
        assert str(conta) == f"{conta.codigo} - {conta.descricao}"

    def test_unique_codigo_per_tenant(self):
        """Should enforce unique codigo per tenant."""
        tenant = TenantFactory()
        PlanoContasFactory(tenant=tenant, codigo="1.01")

        with pytest.raises(IntegrityError):
            PlanoContasFactory(tenant=tenant, codigo="1.01")

    def test_allows_duplicate_codigo_different_tenants(self):
        """Should allow same codigo for different tenants."""
        tenant1 = TenantFactory()
        tenant2 = TenantFactory()

        c1 = PlanoContasFactory(tenant=tenant1, codigo="1.01")
        c2 = PlanoContasFactory(tenant=tenant2, codigo="1.01")

        assert c1.pk is not None
        assert c2.pk is not None

    def test_hierarquia_contas(self):
        """Should handle parent/child relationship."""
        pai = PlanoContasFactory(codigo="1", nivel=1)
        filho = PlanoContasFactory(codigo="1.1", nivel=2, conta_pai=pai)

        assert filho.conta_pai == pai
        assert filho in pai.subcontas.all()


@pytest.mark.django_db
class TestCentroCusto:
    """Tests for CentroCusto model."""

    def test_create_centro_custo(self):
        """Should create a CentroCusto instance."""
        cc = CentroCustoFactory()
        assert cc.pk is not None
        assert str(cc) == f"{cc.codigo} - {cc.descricao}"

    def test_unique_codigo_per_tenant(self):
        """Should enforce unique codigo per tenant."""
        tenant = TenantFactory()
        CentroCustoFactory(tenant=tenant, codigo="CC-01")

        with pytest.raises(IntegrityError):
            CentroCustoFactory(tenant=tenant, codigo="CC-01")


@pytest.mark.django_db
class TestLancamentoContabil:
    """Tests for LancamentoContabil model."""

    def test_create_lancamento(self):
        """Should create a LancamentoContabil instance."""
        lancamento = LancamentoContabilFactory()
        assert lancamento.pk is not None
        assert str(lancamento.data_lancamento) in str(lancamento)

    def test_create_with_partidas(self):
        """Should ensure validation of partidas creation."""
        lancamento = LancamentoContabilFactory()
        p1 = PartidaLancamentoFactory(lancamento=lancamento, tipo="D", valor=50)
        p2 = PartidaLancamentoFactory(lancamento=lancamento, tipo="C", valor=50)

        assert lancamento.partidas.count() == 2
        assert p1.lancamento == lancamento
        assert p2.lancamento == lancamento

    def test_estorno_relationship(self):
        """Should handle estorno relationship."""
        original = LancamentoContabilFactory()
        estorno = LancamentoContabilFactory(estornado=True, lancamento_estorno=original)

        assert estorno.lancamento_estorno == original
        assert estorno in original.estorno_de.all()


@pytest.mark.django_db
class TestPartidaLancamento:
    """Tests for PartidaLancamento model."""

    def test_create_partida(self):
        """Should create a PartidaLancamento instance."""
        partida = PartidaLancamentoFactory()
        assert partida.pk is not None
        assert (
            str(partida)
            == f"{partida.get_tipo_display()} {partida.conta.codigo} R$ {partida.valor}"
        )
