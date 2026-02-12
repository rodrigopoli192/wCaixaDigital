"""
Tests for nfse/reports.py — CSV export, dashboard, API log.
Tests for nfse/signals.py — auto-emission signal.
Tests for nfse/tasks.py — poll_nfse_status.
"""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, TestCase
from django.utils import timezone

from caixa_nfse.nfse.models import (
    EventoFiscal,
    NotaFiscalServico,
    StatusNFSe,
)
from caixa_nfse.nfse.reports import NFSeDashboardView, NFSeExportCSVView
from caixa_nfse.nfse.signals import _deve_gerar_nfse, auto_emitir_nfse
from caixa_nfse.nfse.tasks import poll_nfse_status
from caixa_nfse.tests.factories import (
    ConfiguracaoNFSeFactory,
    NotaFiscalServicoFactory,
    TenantFactory,
    UserFactory,
)

# ── CSV Export Tests ───────────────────────────────────────


class TestNFSeExportCSV(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.tenant = TenantFactory()
        self.user = UserFactory(tenant=self.tenant, pode_emitir_nfse=True)

    def test_export_csv_returns_csv(self):
        NotaFiscalServicoFactory(tenant=self.tenant, status=StatusNFSe.AUTORIZADA)
        NotaFiscalServicoFactory(tenant=self.tenant, status=StatusNFSe.RASCUNHO)

        request = self.factory.get("/nfse/export/csv/")
        request.user = self.user

        view = NFSeExportCSVView()
        view.request = request
        view.kwargs = {}
        response = view.get(request)

        assert response.status_code == 200
        assert "text/csv" in response["Content-Type"]
        assert "nfse_export.csv" in response["Content-Disposition"]

        content = response.content.decode("utf-8-sig")
        lines = [l for l in content.strip().split("\r\n") if l.strip()]
        if len(lines) < 2:
            lines = [l for l in content.strip().split("\n") if l.strip()]
        assert len(lines) >= 2  # Header + at least 1 row

    def test_export_csv_with_status_filter(self):
        NotaFiscalServicoFactory(tenant=self.tenant, status=StatusNFSe.AUTORIZADA)
        NotaFiscalServicoFactory(tenant=self.tenant, status=StatusNFSe.RASCUNHO)

        request = self.factory.get("/nfse/export/csv/?status=AUTORIZADA")
        request.user = self.user

        view = NFSeExportCSVView()
        view.request = request
        view.kwargs = {}
        response = view.get(request)

        content = response.content.decode("utf-8-sig")
        lines = [l for l in content.strip().split("\r\n") if l.strip()]
        if len(lines) < 2:
            lines = [l for l in content.strip().split("\n") if l.strip()]
        # Header + 1 AUTORIZADA row only
        assert len(lines) == 2

    def test_export_csv_empty(self):
        request = self.factory.get("/nfse/export/csv/")
        request.user = self.user

        view = NFSeExportCSVView()
        view.request = request
        view.kwargs = {}
        response = view.get(request)

        content = response.content.decode("utf-8-sig")
        lines = [l for l in content.strip().split("\r\n") if l.strip()]
        if len(lines) < 1:
            lines = [l for l in content.strip().split("\n") if l.strip()]
        assert len(lines) == 1  # Header only


# ── Dashboard Tests ────────────────────────────────────────


class TestNFSeDashboard(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.tenant = TenantFactory()
        self.user = UserFactory(tenant=self.tenant, pode_emitir_nfse=True)

    def test_dashboard_context_has_kpis(self):
        NotaFiscalServicoFactory(
            tenant=self.tenant,
            status=StatusNFSe.AUTORIZADA,
            valor_servicos=Decimal("1000.00"),
        )

        request = self.factory.get("/nfse/dashboard/")
        request.user = self.user

        view = NFSeDashboardView()
        view.request = request
        view.kwargs = {}
        ctx = view.get_context_data()

        assert "kpis" in ctx
        assert ctx["kpis"]["total_notas"] >= 1
        assert ctx["kpis"]["autorizadas"] >= 1

    def test_dashboard_with_month_filter(self):
        request = self.factory.get("/nfse/dashboard/?meses=6")
        request.user = self.user

        view = NFSeDashboardView()
        view.request = request
        view.kwargs = {}
        ctx = view.get_context_data()

        assert ctx["meses"] == 6

    def test_dashboard_empty_data(self):
        request = self.factory.get("/nfse/dashboard/")
        request.user = self.user

        view = NFSeDashboardView()
        view.request = request
        view.kwargs = {}
        ctx = view.get_context_data()

        assert ctx["kpis"]["total_notas"] == 0
        assert "monthly_data" in ctx
        assert "top_clients" in ctx


# ── Signal Tests ────────────────────────────────────────────


class TestAutoEmitirSignal(TestCase):
    def setUp(self):
        self.tenant = TenantFactory()

    def test_deve_gerar_nfse_true_when_enabled(self):
        ConfiguracaoNFSeFactory(
            tenant=self.tenant,
            gerar_nfse_ao_confirmar=True,
        )
        assert _deve_gerar_nfse(self.tenant) is True

    def test_deve_gerar_nfse_false_when_disabled(self):
        ConfiguracaoNFSeFactory(
            tenant=self.tenant,
            gerar_nfse_ao_confirmar=False,
        )
        assert _deve_gerar_nfse(self.tenant) is False

    def test_deve_gerar_nfse_false_when_no_config(self):
        assert _deve_gerar_nfse(self.tenant) is False

    @patch("caixa_nfse.nfse.tasks.emitir_nfse_movimento")
    def test_signal_triggers_task(self, mock_task):
        """Test that the signal dispatches the Celery task."""
        ConfiguracaoNFSeFactory(
            tenant=self.tenant,
            gerar_nfse_ao_confirmar=True,
        )
        mock_instance = MagicMock()
        mock_instance.nota_fiscal_id = None
        mock_instance.cliente_id = 123
        mock_instance.pk = "test-pk"
        mock_instance.tenant = self.tenant

        # Use TestCase.captureOnCommitCallbacks to test on_commit
        with self.captureOnCommitCallbacks(execute=True):
            auto_emitir_nfse(
                sender=None,
                instance=mock_instance,
                created=True,
            )

        mock_task.delay.assert_called_once_with("test-pk")

    def test_signal_skips_when_not_created(self):
        mock_instance = MagicMock()
        mock_instance.nota_fiscal_id = None
        mock_instance.cliente_id = 123
        mock_instance.tenant = self.tenant

        # Should not raise, just return early
        auto_emitir_nfse(
            sender=None,
            instance=mock_instance,
            created=False,
        )

    def test_signal_skips_when_already_has_nota(self):
        mock_instance = MagicMock()
        mock_instance.nota_fiscal_id = "existing-nota"
        mock_instance.tenant = self.tenant

        auto_emitir_nfse(
            sender=None,
            instance=mock_instance,
            created=True,
        )

    def test_signal_skips_when_no_cliente(self):
        mock_instance = MagicMock()
        mock_instance.nota_fiscal_id = None
        mock_instance.cliente_id = None
        mock_instance.tenant = self.tenant

        auto_emitir_nfse(
            sender=None,
            instance=mock_instance,
            created=True,
        )


# ── Polling Task Tests ──────────────────────────────────────


class TestPollNfseStatus(TestCase):
    def setUp(self):
        self.tenant = TenantFactory()
        ConfiguracaoNFSeFactory(tenant=self.tenant, backend="mock")

    def test_poll_updates_autorizada(self):
        nota = NotaFiscalServicoFactory(
            tenant=self.tenant,
            status=StatusNFSe.ENVIANDO,
        )
        # Backdate updated_at
        NotaFiscalServico.objects.filter(pk=nota.pk).update(
            updated_at=timezone.now() - timedelta(minutes=5),
        )

        mock_result = MagicMock()
        mock_result.sucesso = True
        mock_result.status = "autorizada"
        mock_result.xml_retorno = "<nfse/>"
        mock_result.mensagem = "OK"

        with patch("caixa_nfse.nfse.tasks.get_backend") as mock_get_backend:
            mock_backend = MagicMock()
            mock_backend.consultar.return_value = mock_result
            mock_get_backend.return_value = mock_backend

            result = poll_nfse_status()

        nota.refresh_from_db()
        assert nota.status == StatusNFSe.AUTORIZADA
        assert result["atualizadas"] == 1
        assert EventoFiscal.objects.filter(nota=nota).exists()

    def test_poll_updates_rejeitada(self):
        nota = NotaFiscalServicoFactory(
            tenant=self.tenant,
            status=StatusNFSe.ENVIANDO,
        )
        NotaFiscalServico.objects.filter(pk=nota.pk).update(
            updated_at=timezone.now() - timedelta(minutes=5),
        )

        mock_result = MagicMock()
        mock_result.sucesso = True
        mock_result.status = "rejeitada"
        mock_result.xml_retorno = "<erro/>"
        mock_result.mensagem = "Dados inválidos"

        with patch("caixa_nfse.nfse.tasks.get_backend") as mock_get_backend:
            mock_backend = MagicMock()
            mock_backend.consultar.return_value = mock_result
            mock_get_backend.return_value = mock_backend

            result = poll_nfse_status()

        nota.refresh_from_db()
        assert nota.status == StatusNFSe.REJEITADA
        assert result["atualizadas"] == 1

    def test_poll_skip_recent_notes(self):
        """Notes sent less than 2 minutes ago should not be polled."""
        NotaFiscalServicoFactory(
            tenant=self.tenant,
            status=StatusNFSe.ENVIANDO,
        )
        # Don't backdate — nota was just created

        result = poll_nfse_status()
        assert result["atualizadas"] == 0

    def test_poll_no_notes(self):
        result = poll_nfse_status()
        assert result["atualizadas"] == 0

    def test_poll_skips_failed_consulta(self):
        nota = NotaFiscalServicoFactory(
            tenant=self.tenant,
            status=StatusNFSe.ENVIANDO,
        )
        NotaFiscalServico.objects.filter(pk=nota.pk).update(
            updated_at=timezone.now() - timedelta(minutes=5),
        )

        mock_result = MagicMock()
        mock_result.sucesso = False

        with patch("caixa_nfse.nfse.tasks.get_backend") as mock_get_backend:
            mock_backend = MagicMock()
            mock_backend.consultar.return_value = mock_result
            mock_get_backend.return_value = mock_backend

            result = poll_nfse_status()

        nota.refresh_from_db()
        assert nota.status == StatusNFSe.ENVIANDO  # Unchanged
        assert result["atualizadas"] == 0
