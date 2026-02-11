"""
Tests for master-detail import architecture (ItemAtoImportado / ItemAtoMovimento).
"""

from decimal import Decimal

import pytest
from django.urls import reverse

from caixa_nfse.caixa.models import (
    AberturaCaixa,
    Caixa,
    ItemAtoImportado,
    ItemAtoMovimento,
    MovimentoCaixa,
    MovimentoImportado,
    StatusCaixa,
)
from caixa_nfse.caixa.services.importador import ImportadorMovimentos
from caixa_nfse.conftest import *  # noqa: F401,F403
from caixa_nfse.core.models import ConexaoExterna, FormaPagamento

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def caixa_aberto(db, tenant, user):
    caixa = Caixa.objects.create(
        tenant=tenant,
        identificador="CX-MD",
        tipo="FISICO",
        status=StatusCaixa.ABERTO,
        operador_atual=user,
        saldo_atual=Decimal("100.00"),
    )
    return caixa


@pytest.fixture
def abertura_md(db, tenant, user, caixa_aberto):
    return AberturaCaixa.objects.create(
        tenant=tenant,
        caixa=caixa_aberto,
        operador=user,
        saldo_abertura=Decimal("100.00"),
        created_by=user,
    )


@pytest.fixture
def conexao_md(db, tenant):
    from caixa_nfse.backoffice.models import Sistema

    sistema = Sistema.objects.create(nome="Sistema MD", ativo=True)
    return ConexaoExterna.objects.create(
        tenant=tenant,
        sistema=sistema,
        tipo_conexao="MSSQL",
        host="localhost",
        porta=1433,
        database="testdb",
        usuario="sa",
        senha="secret",
    )


@pytest.fixture
def rotina_md(db, conexao_md):
    from caixa_nfse.backoffice.models import Rotina

    return Rotina.objects.create(
        sistema=conexao_md.sistema,
        nome="Rotina Atos",
        sql_content="SELECT * FROM atos",
        ativo=True,
    )


@pytest.fixture
def forma_md(db, tenant):
    return FormaPagamento.objects.create(tenant=tenant, nome="Dinheiro", ativo=True)


# ===========================================================================
# salvar_importacao creates children
# ===========================================================================


@pytest.mark.django_db
class TestSalvarImportacaoCreatesChildren:
    def test_single_protocol_creates_parent_and_children(
        self, abertura_md, conexao_md, rotina_md, user
    ):
        headers = ["PROTOCOLO", "VALOR", "ISS", "DESCRICAO", "EMOLUMENTO"]
        rows = [
            ("PROT-001", "100.00", "10.00", "Escritura A", "50.00"),
            ("PROT-001", "200.00", "20.00", "Registro B", "80.00"),
        ]

        count, skipped = ImportadorMovimentos.salvar_importacao(
            abertura_md, conexao_md, rotina_md, headers, rows, user
        )

        assert count == 1
        assert skipped == 0

        parent = MovimentoImportado.objects.get(protocolo="PROT-001")
        assert parent.valor == Decimal("300.00")
        assert parent.iss == Decimal("30.00")
        assert parent.emolumento == Decimal("130.00")

        children = list(parent.itens.all().order_by("created_at"))
        assert len(children) == 2

        assert children[0].descricao == "Escritura A"
        assert children[0].valor == Decimal("100.00")
        assert children[0].iss == Decimal("10.00")
        assert children[0].emolumento == Decimal("50.00")

        assert children[1].descricao == "Registro B"
        assert children[1].valor == Decimal("200.00")

    def test_multiple_protocols_create_separate_parents(
        self, abertura_md, conexao_md, rotina_md, user
    ):
        headers = ["PROTOCOLO", "VALOR", "DESCRICAO"]
        rows = [
            ("PROT-A", "100.00", "Ato A1"),
            ("PROT-A", "50.00", "Ato A2"),
            ("PROT-B", "300.00", "Ato B1"),
        ]

        count, skipped = ImportadorMovimentos.salvar_importacao(
            abertura_md, conexao_md, rotina_md, headers, rows, user
        )

        assert count == 2

        parent_a = MovimentoImportado.objects.get(protocolo="PROT-A")
        assert parent_a.valor == Decimal("150.00")
        assert parent_a.itens.count() == 2

        parent_b = MovimentoImportado.objects.get(protocolo="PROT-B")
        assert parent_b.valor == Decimal("300.00")
        assert parent_b.itens.count() == 1


# ===========================================================================
# confirmar_movimentos copies children
# ===========================================================================


@pytest.mark.django_db
class TestConfirmarCopiesChildren:
    def test_confirm_copies_children(self, tenant, abertura_md, forma_md, user):
        imp = MovimentoImportado.objects.create(
            tenant=tenant,
            abertura=abertura_md,
            protocolo="PROT-CONFIRM",
            valor=Decimal("250.00"),
            iss=Decimal("25.00"),
            descricao="Test Import",
        )
        ItemAtoImportado.objects.create(
            tenant=tenant,
            movimento_importado=imp,
            descricao="Ato 1",
            valor=Decimal("100.00"),
            iss=Decimal("10.00"),
            emolumento=Decimal("40.00"),
        )
        ItemAtoImportado.objects.create(
            tenant=tenant,
            movimento_importado=imp,
            descricao="Ato 2",
            valor=Decimal("150.00"),
            iss=Decimal("15.00"),
            emolumento=Decimal("60.00"),
        )

        confirmed = ImportadorMovimentos.confirmar_movimentos(
            ids=[imp.pk],
            abertura=abertura_md,
            forma_pagamento=forma_md,
            tipo="ENTRADA",
            user=user,
        )

        assert confirmed == 1

        imp.refresh_from_db()
        assert imp.confirmado is True
        assert imp.movimento_destino is not None

        mov_items = list(imp.movimento_destino.itens.all().order_by("created_at"))
        assert len(mov_items) == 2
        assert mov_items[0].descricao == "Ato 1"
        assert mov_items[0].valor == Decimal("100.00")
        assert mov_items[1].descricao == "Ato 2"
        assert mov_items[1].valor == Decimal("150.00")

    def test_confirm_without_children_works(self, tenant, abertura_md, forma_md, user):
        """Old-style import without children must still work."""
        imp = MovimentoImportado.objects.create(
            tenant=tenant,
            abertura=abertura_md,
            protocolo="PROT-LEGACY",
            valor=Decimal("500.00"),
            descricao="Legacy Import",
        )

        confirmed = ImportadorMovimentos.confirmar_movimentos(
            ids=[imp.pk],
            abertura=abertura_md,
            forma_pagamento=forma_md,
            tipo="ENTRADA",
            user=user,
        )

        assert confirmed == 1
        imp.refresh_from_db()
        assert imp.movimento_destino.itens.count() == 0


# ===========================================================================
# Recibo detalhado view
# ===========================================================================


@pytest.mark.django_db
class TestReciboDetalhadoView:
    @pytest.fixture(autouse=True)
    def _setup(self, tenant, abertura_md, forma_md, user, client):
        self.client = client
        self.client.force_login(user)
        self.mov = MovimentoCaixa.objects.create(
            tenant=tenant,
            abertura=abertura_md,
            tipo="ENTRADA",
            forma_pagamento=forma_md,
            valor=Decimal("300.00"),
            protocolo="PROT-RECIBO",
            descricao="Test Recibo",
            created_by=user,
        )
        ItemAtoMovimento.objects.create(
            tenant=tenant,
            movimento=self.mov,
            descricao="Ato Recibo 1",
            valor=Decimal("100.00"),
            emolumento=Decimal("40.00"),
        )
        ItemAtoMovimento.objects.create(
            tenant=tenant,
            movimento=self.mov,
            descricao="Ato Recibo 2",
            valor=Decimal("200.00"),
            emolumento=Decimal("80.00"),
        )

    def test_html_recibo(self):
        url = reverse("caixa:recibo_detalhado", kwargs={"pk": self.mov.pk})
        resp = self.client.get(url)
        assert resp.status_code == 200
        assert b"Ato Recibo 1" in resp.content
        assert b"Ato Recibo 2" in resp.content
        assert b"PROT-RECIBO" in resp.content

    def test_html_recibo_no_children_fallback(self, tenant, abertura_md, forma_md, user):
        mov_no_items = MovimentoCaixa.objects.create(
            tenant=tenant,
            abertura=abertura_md,
            tipo="ENTRADA",
            forma_pagamento=forma_md,
            valor=Decimal("500.00"),
            protocolo="PROT-LEGACY",
            descricao="No Items",
            created_by=user,
        )
        url = reverse("caixa:recibo_detalhado", kwargs={"pk": mov_no_items.pk})
        resp = self.client.get(url)
        assert resp.status_code == 200
        assert "detalhamento" in resp.content.decode()


# ===========================================================================
# Manual movement has no children
# ===========================================================================


@pytest.mark.django_db
class TestManualMovementNoChildren:
    def test_manual_movement_has_no_children(self, tenant, abertura_md, forma_md, user):
        mov = MovimentoCaixa.objects.create(
            tenant=tenant,
            abertura=abertura_md,
            tipo="ENTRADA",
            forma_pagamento=forma_md,
            valor=Decimal("100.00"),
            descricao="Manual Entry",
            created_by=user,
        )
        assert mov.itens.count() == 0
