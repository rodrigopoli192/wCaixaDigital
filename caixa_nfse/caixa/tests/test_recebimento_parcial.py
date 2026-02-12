"""
Tests for partial payment functionality (recebimento parcial).
Covers: parcelas_map, ParcelaRecebimento, StatusRecebimento transitions,
NFS-e only on quitação, migrar_pendentes_para_nova_abertura,
and Notificacao model/management command.
"""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest

from caixa_nfse.backoffice.models import Rotina, Sistema
from caixa_nfse.caixa.models import (
    AberturaCaixa,
    Caixa,
    MovimentoCaixa,
    MovimentoImportado,
    ParcelaRecebimento,
    StatusCaixa,
    StatusRecebimento,
    TipoMovimento,
)
from caixa_nfse.caixa.services.importador import ImportadorMovimentos
from caixa_nfse.conftest import *  # noqa: F401,F403
from caixa_nfse.core.models import ConexaoExterna, FormaPagamento, Notificacao, TipoNotificacao

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sistema_rp(db):
    return Sistema.objects.create(nome="RP-Test", ativo=True)


@pytest.fixture
def conexao_rp(db, tenant, sistema_rp):
    return ConexaoExterna.objects.create(
        tenant=tenant,
        sistema=sistema_rp,
        tipo_conexao="MSSQL",
        host="10.0.0.1",
        porta=1433,
        database="DB_TEST",
        usuario="sa",
        senha="secret",
    )


@pytest.fixture
def rotina_rp(db, sistema_rp):
    return Rotina.objects.create(
        sistema=sistema_rp, nome="Rotina RP", sql_content="SELECT 1", ativo=True
    )


@pytest.fixture
def caixa_rp(db, tenant, admin_user):
    return Caixa.objects.create(
        tenant=tenant,
        identificador="CX-RP",
        tipo="FISICO",
        status=StatusCaixa.ABERTO,
        operador_atual=admin_user,
        saldo_atual=Decimal("1000.00"),
    )


@pytest.fixture
def abertura_rp(db, tenant, admin_user, caixa_rp):
    return AberturaCaixa.objects.create(
        tenant=tenant,
        caixa=caixa_rp,
        operador=admin_user,
        saldo_abertura=Decimal("1000.00"),
        created_by=admin_user,
    )


@pytest.fixture
def forma_pgto(db, tenant):
    return FormaPagamento.objects.create(tenant=tenant, nome="Dinheiro RP", ativo=True)


@pytest.fixture
def importado(db, tenant, abertura_rp, conexao_rp, rotina_rp, admin_user):
    return MovimentoImportado.objects.create(
        tenant=tenant,
        abertura=abertura_rp,
        conexao=conexao_rp,
        rotina=rotina_rp,
        importado_por=admin_user,
        protocolo="RP-001",
        valor=Decimal("300.00"),
        descricao="Protocolo para teste parcial",
    )


# ===========================================================================
# Partial Payment Tests
# ===========================================================================


@pytest.mark.django_db
class TestParcialPayment:
    """Tests for partial payment via parcelas_map."""

    def test_partial_payment_creates_parcela(self, abertura_rp, forma_pgto, admin_user, importado):
        """Paying R$100 of R$300 should create PARCIAL status and a ParcelaRecebimento."""
        parcelas_map = {str(importado.pk): Decimal("100.00")}
        count = ImportadorMovimentos.confirmar_movimentos(
            [importado.pk],
            abertura_rp,
            forma_pgto,
            TipoMovimento.ENTRADA,
            admin_user,
            parcelas_map=parcelas_map,
        )
        assert count == 1

        importado.refresh_from_db()
        assert importado.status_recebimento == StatusRecebimento.PARCIAL
        assert importado.confirmado is False  # Not fully paid

        parcelas = ParcelaRecebimento.objects.filter(movimento_importado=importado)
        assert parcelas.count() == 1
        parcela = parcelas.first()
        assert parcela.valor == Decimal("100.00")
        assert parcela.numero_parcela == 1

    def test_full_payment_creates_quitado(self, abertura_rp, forma_pgto, admin_user, importado):
        """Paying full amount should create QUITADO status."""
        parcelas_map = {str(importado.pk): Decimal("300.00")}
        count = ImportadorMovimentos.confirmar_movimentos(
            [importado.pk],
            abertura_rp,
            forma_pgto,
            TipoMovimento.ENTRADA,
            admin_user,
            parcelas_map=parcelas_map,
        )
        assert count == 1

        importado.refresh_from_db()
        assert importado.status_recebimento == StatusRecebimento.QUITADO
        assert importado.confirmado is True
        assert importado.movimento_destino is not None

    def test_no_parcelas_map_pays_full(self, abertura_rp, forma_pgto, admin_user, importado):
        """Without parcelas_map, should pay full amount (backward compatibility)."""
        count = ImportadorMovimentos.confirmar_movimentos(
            [importado.pk],
            abertura_rp,
            forma_pgto,
            TipoMovimento.ENTRADA,
            admin_user,
        )
        assert count == 1

        importado.refresh_from_db()
        assert importado.status_recebimento == StatusRecebimento.QUITADO
        assert importado.confirmado is True

    def test_multi_parcela_flow(self, abertura_rp, forma_pgto, admin_user, importado):
        """Multiple partial payments should accumulate and eventually quitado."""
        # First partial
        parcelas_map = {str(importado.pk): Decimal("100.00")}
        ImportadorMovimentos.confirmar_movimentos(
            [importado.pk],
            abertura_rp,
            forma_pgto,
            TipoMovimento.ENTRADA,
            admin_user,
            parcelas_map=parcelas_map,
        )
        importado.refresh_from_db()
        assert importado.status_recebimento == StatusRecebimento.PARCIAL
        assert importado.valor_recebido == Decimal("100.00")
        assert importado.saldo_pendente == Decimal("200.00")

        # Second partial
        parcelas_map = {str(importado.pk): Decimal("100.00")}
        ImportadorMovimentos.confirmar_movimentos(
            [importado.pk],
            abertura_rp,
            forma_pgto,
            TipoMovimento.ENTRADA,
            admin_user,
            parcelas_map=parcelas_map,
        )
        importado.refresh_from_db()
        assert importado.status_recebimento == StatusRecebimento.PARCIAL
        assert importado.valor_recebido == Decimal("200.00")

        # Final payment (quitação)
        parcelas_map = {str(importado.pk): Decimal("200.00")}
        ImportadorMovimentos.confirmar_movimentos(
            [importado.pk],
            abertura_rp,
            forma_pgto,
            TipoMovimento.ENTRADA,
            admin_user,
            parcelas_map=parcelas_map,
        )
        importado.refresh_from_db()
        assert importado.status_recebimento == StatusRecebimento.QUITADO
        assert importado.confirmado is True
        assert ParcelaRecebimento.objects.filter(movimento_importado=importado).count() == 3

    def test_parcela_numbering(self, abertura_rp, forma_pgto, admin_user, importado):
        """Parcela numbers should auto-increment."""
        for i in range(3):
            parcelas_map = {str(importado.pk): Decimal("100.00")}
            ImportadorMovimentos.confirmar_movimentos(
                [importado.pk],
                abertura_rp,
                forma_pgto,
                TipoMovimento.ENTRADA,
                admin_user,
                parcelas_map=parcelas_map,
            )

        parcelas = ParcelaRecebimento.objects.filter(movimento_importado=importado).order_by(
            "numero_parcela"
        )
        assert [p.numero_parcela for p in parcelas] == [1, 2, 3]


# ===========================================================================
# NFS-e Generation Tests
# ===========================================================================


@pytest.mark.django_db
class TestNfseGeneration:
    """NFS-e should only be generated on quitação."""

    @patch("caixa_nfse.caixa.services.importador._deve_gerar_nfse", return_value=True)
    @patch("caixa_nfse.nfse.tasks.emitir_nfse_movimento")
    def test_nfse_not_called_on_partial(
        self, mock_task, mock_config, abertura_rp, forma_pgto, admin_user, importado
    ):
        parcelas_map = {str(importado.pk): Decimal("100.00")}
        ImportadorMovimentos.confirmar_movimentos(
            [importado.pk],
            abertura_rp,
            forma_pgto,
            TipoMovimento.ENTRADA,
            admin_user,
            parcelas_map=parcelas_map,
        )
        mock_task.delay.assert_not_called()

    @patch("caixa_nfse.caixa.services.importador._deve_gerar_nfse", return_value=False)
    def test_nfse_not_dispatched_without_config(
        self, mock_config, abertura_rp, forma_pgto, admin_user, importado
    ):
        """Without NFS-e config, should not dispatch tasks even on quitação."""
        parcelas_map = {str(importado.pk): Decimal("300.00")}
        ImportadorMovimentos.confirmar_movimentos(
            [importado.pk],
            abertura_rp,
            forma_pgto,
            TipoMovimento.ENTRADA,
            admin_user,
            parcelas_map=parcelas_map,
        )
        # No exception raised, no task dispatched


# ===========================================================================
# Model Properties Tests
# ===========================================================================


@pytest.mark.django_db
class TestModelProperties:
    """Tests for computed properties on MovimentoImportado."""

    def test_valor_recebido_zero_initially(self, importado):
        assert importado.valor_recebido == Decimal("0.00")

    def test_saldo_pendente_equals_valor_initially(self, importado):
        assert importado.saldo_pendente == Decimal("300.00")

    def test_percentual_recebido_zero(self, importado):
        assert importado.percentual_recebido == 0

    def test_prazo_vencido_no_deadline(self, importado):
        assert importado.prazo_vencido is False

    def test_prazo_vencido_past_deadline(self, importado):
        importado.prazo_quitacao = date.today() - timedelta(days=1)
        importado.save()
        assert importado.prazo_vencido is True

    def test_prazo_not_vencido_if_quitado(self, importado):
        importado.prazo_quitacao = date.today() - timedelta(days=1)
        importado.status_recebimento = StatusRecebimento.QUITADO
        importado.save()
        assert importado.prazo_vencido is False

    def test_percentual_zero_value(self, importado):
        importado.valor = Decimal("0.00")
        importado.save()
        assert importado.percentual_recebido == 0


# ===========================================================================
# Cross-Session Migration Tests
# ===========================================================================


@pytest.mark.django_db
class TestMigrarPendentes:
    """Tests for migrar_pendentes_para_nova_abertura."""

    def test_migrates_pending_from_closed_session(
        self, tenant, admin_user, caixa_rp, conexao_rp, rotina_rp
    ):
        # Create old closed abertura
        old_abertura = AberturaCaixa.objects.create(
            tenant=tenant,
            caixa=caixa_rp,
            operador=admin_user,
            saldo_abertura=Decimal("0.00"),
            created_by=admin_user,
        )

        imp = MovimentoImportado.objects.create(
            tenant=tenant,
            abertura=old_abertura,
            conexao=conexao_rp,
            rotina=rotina_rp,
            importado_por=admin_user,
            protocolo="MIG-001",
            valor=Decimal("100.00"),
            status_recebimento=StatusRecebimento.PENDENTE,
        )

        # Close old abertura via FechamentoCaixa
        from caixa_nfse.caixa.models import FechamentoCaixa

        FechamentoCaixa.objects.create(
            tenant=tenant,
            abertura=old_abertura,
            operador=admin_user,
            saldo_sistema=Decimal("0.00"),
            saldo_informado=Decimal("0.00"),
            diferenca=Decimal("0.00"),
            status="APROVADO",
        )

        # Create new abertura
        new_abertura = AberturaCaixa.objects.create(
            tenant=tenant,
            caixa=caixa_rp,
            operador=admin_user,
            saldo_abertura=Decimal("0.00"),
            created_by=admin_user,
        )

        count = ImportadorMovimentos.migrar_pendentes_para_nova_abertura(new_abertura)
        assert count == 1

        imp.refresh_from_db()
        assert imp.abertura == new_abertura

    def test_does_not_migrate_quitado(self, tenant, admin_user, caixa_rp, conexao_rp, rotina_rp):
        old_abertura = AberturaCaixa.objects.create(
            tenant=tenant,
            caixa=caixa_rp,
            operador=admin_user,
            saldo_abertura=Decimal("0.00"),
            created_by=admin_user,
        )

        MovimentoImportado.objects.create(
            tenant=tenant,
            abertura=old_abertura,
            conexao=conexao_rp,
            rotina=rotina_rp,
            importado_por=admin_user,
            protocolo="MIG-002",
            valor=Decimal("50.00"),
            status_recebimento=StatusRecebimento.QUITADO,
            confirmado=True,
        )

        from caixa_nfse.caixa.models import FechamentoCaixa

        FechamentoCaixa.objects.create(
            tenant=tenant,
            abertura=old_abertura,
            operador=admin_user,
            saldo_sistema=Decimal("0.00"),
            saldo_informado=Decimal("0.00"),
            diferenca=Decimal("0.00"),
            status="APROVADO",
        )

        new_abertura = AberturaCaixa.objects.create(
            tenant=tenant,
            caixa=caixa_rp,
            operador=admin_user,
            saldo_abertura=Decimal("0.00"),
            created_by=admin_user,
        )

        count = ImportadorMovimentos.migrar_pendentes_para_nova_abertura(new_abertura)
        assert count == 0

    def test_migrates_parcial(self, tenant, admin_user, caixa_rp, conexao_rp, rotina_rp):
        old_abertura = AberturaCaixa.objects.create(
            tenant=tenant,
            caixa=caixa_rp,
            operador=admin_user,
            saldo_abertura=Decimal("0.00"),
            created_by=admin_user,
        )

        imp = MovimentoImportado.objects.create(
            tenant=tenant,
            abertura=old_abertura,
            conexao=conexao_rp,
            rotina=rotina_rp,
            importado_por=admin_user,
            protocolo="MIG-003",
            valor=Decimal("200.00"),
            status_recebimento=StatusRecebimento.PARCIAL,
        )

        from caixa_nfse.caixa.models import FechamentoCaixa

        FechamentoCaixa.objects.create(
            tenant=tenant,
            abertura=old_abertura,
            operador=admin_user,
            saldo_sistema=Decimal("0.00"),
            saldo_informado=Decimal("0.00"),
            diferenca=Decimal("0.00"),
            status="APROVADO",
        )

        new_abertura = AberturaCaixa.objects.create(
            tenant=tenant,
            caixa=caixa_rp,
            operador=admin_user,
            saldo_abertura=Decimal("0.00"),
            created_by=admin_user,
        )

        count = ImportadorMovimentos.migrar_pendentes_para_nova_abertura(new_abertura)
        assert count == 1
        imp.refresh_from_db()
        assert imp.abertura == new_abertura


# ===========================================================================
# Notification Model Tests
# ===========================================================================


@pytest.mark.django_db
class TestNotificacao:
    """Tests for Notificacao model."""

    def test_create_notification(self, tenant):
        n = Notificacao.objects.create(
            tenant=tenant,
            tipo=TipoNotificacao.PROTOCOLO_VENCIDO,
            titulo="Test notification",
            mensagem="Test message",
        )
        assert n.lida is False
        assert str(n) == "[Protocolo vencido] Test notification"

    def test_marcar_lida(self, tenant):
        n = Notificacao.objects.create(
            tenant=tenant,
            tipo=TipoNotificacao.GERAL,
            titulo="Test",
            mensagem="Message",
        )
        n.marcar_lida()
        n.refresh_from_db()
        assert n.lida is True
        assert n.lida_em is not None


# ===========================================================================
# Management Command Tests
# ===========================================================================


@pytest.mark.django_db
class TestVerificarPrazosCommand:
    """Tests for verificar_prazos_protocolos management command."""

    def test_marks_overdue_as_vencido(
        self, tenant, admin_user, caixa_rp, abertura_rp, conexao_rp, rotina_rp
    ):
        imp = MovimentoImportado.objects.create(
            tenant=tenant,
            abertura=abertura_rp,
            conexao=conexao_rp,
            rotina=rotina_rp,
            importado_por=admin_user,
            protocolo="PRAZO-001",
            valor=Decimal("100.00"),
            status_recebimento=StatusRecebimento.PENDENTE,
            prazo_quitacao=date.today() - timedelta(days=1),
        )

        from django.core.management import call_command

        call_command("verificar_prazos_protocolos")

        imp.refresh_from_db()
        assert imp.status_recebimento == StatusRecebimento.VENCIDO

        # Should also create notification
        assert Notificacao.objects.filter(
            tipo=TipoNotificacao.PROTOCOLO_VENCIDO,
            referencia_id=str(imp.pk),
        ).exists()

    def test_creates_alert_for_expiring_soon(
        self, tenant, admin_user, caixa_rp, abertura_rp, conexao_rp, rotina_rp
    ):
        imp = MovimentoImportado.objects.create(
            tenant=tenant,
            abertura=abertura_rp,
            conexao=conexao_rp,
            rotina=rotina_rp,
            importado_por=admin_user,
            protocolo="PRAZO-002",
            valor=Decimal("100.00"),
            status_recebimento=StatusRecebimento.PARCIAL,
            prazo_quitacao=date.today() + timedelta(days=2),
        )

        from django.core.management import call_command

        call_command("verificar_prazos_protocolos")

        # Should NOT mark as vencido (still within deadline)
        imp.refresh_from_db()
        assert imp.status_recebimento == StatusRecebimento.PARCIAL

        # Should create "vencendo" notification
        assert Notificacao.objects.filter(
            tipo=TipoNotificacao.PROTOCOLO_VENCENDO,
            referencia_id=str(imp.pk),
        ).exists()


# ===========================================================================
# ParcelaRecebimento Model Tests
# ===========================================================================


@pytest.mark.django_db
class TestParcelaRecebimento:
    """Tests for ParcelaRecebimento model."""

    def test_str_representation(self, abertura_rp, forma_pgto, admin_user, importado):
        parcela = ParcelaRecebimento.objects.create(
            tenant=importado.tenant,
            movimento_importado=importado,
            movimento_caixa=MovimentoCaixa.objects.create(
                tenant=importado.tenant,
                abertura=abertura_rp,
                valor=Decimal("100.00"),
                tipo=TipoMovimento.ENTRADA,
                descricao="Test",
                forma_pagamento=forma_pgto,
            ),
            abertura=abertura_rp,
            forma_pagamento=forma_pgto,
            valor=Decimal("100.00"),
            numero_parcela=1,
            recebido_por=admin_user,
        )
        assert "Parcela 1" in str(parcela)
        assert "R$ 100.00" in str(parcela)

    def test_ordering(self, abertura_rp, forma_pgto, admin_user, importado):
        for i in range(3):
            mov = MovimentoCaixa.objects.create(
                tenant=importado.tenant,
                abertura=abertura_rp,
                valor=Decimal("100.00"),
                tipo=TipoMovimento.ENTRADA,
                descricao=f"Test {i}",
                forma_pagamento=forma_pgto,
            )
            ParcelaRecebimento.objects.create(
                tenant=importado.tenant,
                movimento_importado=importado,
                movimento_caixa=mov,
                abertura=abertura_rp,
                forma_pagamento=forma_pgto,
                valor=Decimal("100.00"),
                numero_parcela=3 - i,  # insert in reverse order
                recebido_por=admin_user,
            )
        # Should be ordered by numero_parcela
        nums = list(
            ParcelaRecebimento.objects.filter(movimento_importado=importado).values_list(
                "numero_parcela", flat=True
            )
        )
        assert nums == [1, 2, 3]
