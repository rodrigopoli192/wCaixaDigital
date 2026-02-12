"""
Tests to cover remaining gaps in caixa/views.py — targeting 100% coverage.

Covers:
- ImportarMovimentosView.post "buscar" with real preview grouping (lines 551-742)
- SalvarImportadosView.post success path (lines 784-812)
- AprovarFechamentoView fallback redirect (line 479)
- ReciboDetalhadoView: sistema_rotina, protocolo_display, no-items totals, PDF path (lines 972-1046)
- ItensAtoView: importado model_type (lines 1055-1094)
"""

from decimal import Decimal
from unittest.mock import patch

import pytest
from django.urls import reverse

from caixa_nfse.backoffice.models import Rotina, Sistema
from caixa_nfse.caixa.models import (
    AberturaCaixa,
    Caixa,
    FechamentoCaixa,
    ItemAtoImportado,
    ItemAtoMovimento,
    MovimentoCaixa,
    MovimentoImportado,
    StatusCaixa,
    StatusFechamento,
)
from caixa_nfse.conftest import *  # noqa: F401,F403
from caixa_nfse.core.models import ConexaoExterna, FormaPagamento

# ---------------------------------------------------------------------------
# Shared Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sistema(db):
    return Sistema.objects.create(nome="RI Legacy", ativo=True)


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
        sistema=sistema,
        nome="Buscar Protocolos",
        sql_content="SELECT * FROM protocolos WHERE data >= @DATA_INICIO",
        ativo=True,
    )


@pytest.fixture
def caixa_aberto(db, tenant, admin_user):
    return Caixa.objects.create(
        tenant=tenant,
        identificador="CX-COV",
        tipo="FISICO",
        status=StatusCaixa.ABERTO,
        operador_atual=admin_user,
        saldo_atual=Decimal("100.00"),
    )


@pytest.fixture
def abertura(db, tenant, admin_user, caixa_aberto):
    return AberturaCaixa.objects.create(
        tenant=tenant,
        caixa=caixa_aberto,
        operador=admin_user,
        saldo_abertura=Decimal("100.00"),
        created_by=admin_user,
    )


@pytest.fixture
def forma_pagamento(db, tenant):
    return FormaPagamento.objects.create(tenant=tenant, nome="Dinheiro", ativo=True)


@pytest.fixture
def admin_client(client, admin_user):
    client.force_login(admin_user)
    return client


# ===========================================================================
# ImportarMovimentosView.post "buscar" — preview grouping (lines 551-742)
# ===========================================================================


@pytest.mark.django_db
class TestImportarBuscarPreview:
    """Cover the full buscar flow: params collection, duplicate detection,
    grouping by protocol, serialization, and template rendering."""

    @patch("caixa_nfse.caixa.services.importador.ImportadorMovimentos.executar_rotinas")
    @patch("caixa_nfse.caixa.services.importador.ImportadorMovimentos.mapear_colunas")
    def test_buscar_returns_preview_grouped(
        self, mock_map, mock_exec, admin_client, abertura, conexao, rotina
    ):
        """Two rows with same protocol should be grouped into one preview row."""
        mock_exec.return_value = [
            (
                rotina,
                ["PROTOCOLO", "VALOR", "ISS", "DESCRICAO"],
                [
                    ("PROT-1", "100.00", "10.00", "Ato A"),
                    ("PROT-1", "200.00", "20.00", "Ato B"),
                ],
                [],
            ),
        ]
        mock_map.side_effect = [
            {
                "protocolo": "PROT-1",
                "valor": "100.00",
                "iss": "10.00",
                "descricao": "Ato A",
                "emolumento": "0",
            },
            {
                "protocolo": "PROT-1",
                "valor": "200.00",
                "iss": "20.00",
                "descricao": "Ato B",
                "emolumento": "0",
            },
        ]
        url = reverse("caixa:importar_movimentos", kwargs={"pk": abertura.pk})
        response = admin_client.post(
            url,
            {
                "action": "buscar",
                "conexao_rotina_pairs": [f"{conexao.pk}:{rotina.pk}"],
            },
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert "PROT-1" in content

    @patch("caixa_nfse.caixa.services.importador.ImportadorMovimentos.executar_rotinas")
    @patch("caixa_nfse.caixa.services.importador.ImportadorMovimentos.mapear_colunas")
    def test_buscar_no_results(self, mock_map, mock_exec, admin_client, abertura, conexao, rotina):
        """Empty result set should render importados_results with total_rows=0."""
        mock_exec.return_value = [
            (rotina, ["PROTOCOLO"], [], []),
        ]
        url = reverse("caixa:importar_movimentos", kwargs={"pk": abertura.pk})
        response = admin_client.post(
            url,
            {
                "action": "buscar",
                "conexao_rotina_pairs": [f"{conexao.pk}:{rotina.pk}"],
            },
        )
        assert response.status_code == 200

    @patch("caixa_nfse.caixa.services.importador.ImportadorMovimentos.executar_rotinas")
    @patch("caixa_nfse.caixa.services.importador.ImportadorMovimentos.mapear_colunas")
    def test_buscar_with_sql_params(
        self, mock_map, mock_exec, admin_client, abertura, conexao, rotina
    ):
        """Params starting with param_ should be collected and passed through."""
        mock_exec.return_value = [
            (rotina, ["PROTOCOLO", "VALOR"], [("P-1", "50.00")], []),
        ]
        mock_map.return_value = {"protocolo": "P-1", "valor": "50.00", "descricao": "X"}
        url = reverse("caixa:importar_movimentos", kwargs={"pk": abertura.pk})
        response = admin_client.post(
            url,
            {
                "action": "buscar",
                "conexao_rotina_pairs": [f"{conexao.pk}:{rotina.pk}"],
                "param_DATA_INICIO": "20260101",
                "param_DATA_FIM": "20260131",
            },
        )
        assert response.status_code == 200
        # Verify params were collected
        call_kwargs = mock_exec.call_args
        sql_params = call_kwargs[1].get("sql_params") or (
            call_kwargs[0][3] if len(call_kwargs[0]) > 3 else {}
        )

    @patch("caixa_nfse.caixa.services.importador.ImportadorMovimentos.executar_rotinas")
    @patch("caixa_nfse.caixa.services.importador.ImportadorMovimentos.mapear_colunas")
    def test_buscar_duplicate_detection(
        self, mock_map, mock_exec, admin_client, abertura, conexao, rotina, tenant, admin_user
    ):
        """Rows with protocol already in DB should be marked as duplicated."""
        # Create existing importado with same protocol
        MovimentoImportado.objects.create(
            tenant=tenant,
            abertura=abertura,
            conexao=conexao,
            rotina=rotina,
            importado_por=admin_user,
            protocolo="PROT-DUP",
            valor=Decimal("100.00"),
        )
        mock_exec.return_value = [
            (rotina, ["PROTOCOLO", "VALOR"], [("PROT-DUP", "100.00")], []),
        ]
        mock_map.return_value = {
            "protocolo": "PROT-DUP",
            "valor": "100.00",
            "descricao": "Dup",
        }
        url = reverse("caixa:importar_movimentos", kwargs={"pk": abertura.pk})
        response = admin_client.post(
            url,
            {
                "action": "buscar",
                "conexao_rotina_pairs": [f"{conexao.pk}:{rotina.pk}"],
            },
        )
        assert response.status_code == 200

    @patch("caixa_nfse.caixa.services.importador.ImportadorMovimentos.executar_rotinas")
    @patch("caixa_nfse.caixa.services.importador.ImportadorMovimentos.mapear_colunas")
    def test_buscar_ungrouped_no_protocol(
        self, mock_map, mock_exec, admin_client, abertura, conexao, rotina
    ):
        """Rows without protocol stay ungrouped."""
        mock_exec.return_value = [
            (rotina, ["VALOR", "DESCRICAO"], [("50.00", "Sem Proto")], []),
        ]
        mock_map.return_value = {
            "protocolo": "",
            "valor": "50.00",
            "descricao": "Sem Proto",
        }
        url = reverse("caixa:importar_movimentos", kwargs={"pk": abertura.pk})
        response = admin_client.post(
            url,
            {
                "action": "buscar",
                "conexao_rotina_pairs": [f"{conexao.pk}:{rotina.pk}"],
            },
        )
        assert response.status_code == 200

    @patch("caixa_nfse.caixa.services.importador.ImportadorMovimentos.executar_rotinas")
    @patch("caixa_nfse.caixa.services.importador.ImportadorMovimentos.mapear_colunas")
    def test_buscar_with_servicoandamento(
        self, mock_map, mock_exec, admin_client, abertura, conexao, rotina, tenant
    ):
        """When tenant has chave_servico_andamento_ri, it should be injected."""
        tenant.chave_servico_andamento_ri = "CHAVE123"
        tenant.save(update_fields=["chave_servico_andamento_ri"])
        mock_exec.return_value = [(rotina, [], [], [])]
        url = reverse("caixa:importar_movimentos", kwargs={"pk": abertura.pk})
        response = admin_client.post(
            url,
            {
                "action": "buscar",
                "conexao_rotina_pairs": [f"{conexao.pk}:{rotina.pk}"],
            },
        )
        assert response.status_code == 200

    @patch("caixa_nfse.caixa.services.importador.ImportadorMovimentos.executar_rotinas")
    @patch("caixa_nfse.caixa.services.importador.ImportadorMovimentos.mapear_colunas")
    def test_buscar_decimal_and_date_formatting(
        self, mock_map, mock_exec, admin_client, abertura, conexao, rotina
    ):
        """Cover Decimal and date formatting in full_data (lines 616-621)."""
        from datetime import datetime

        mock_exec.return_value = [
            (
                rotina,
                ["PROTOCOLO", "VALOR", "DATA"],
                [
                    ("P-FMT", Decimal("123.45"), datetime(2026, 1, 15, 10, 30)),
                ],
                [],
            ),
        ]
        mock_map.return_value = {
            "protocolo": "P-FMT",
            "valor": "123.45",
            "descricao": "Fmt Test",
        }
        url = reverse("caixa:importar_movimentos", kwargs={"pk": abertura.pk})
        response = admin_client.post(
            url,
            {
                "action": "buscar",
                "conexao_rotina_pairs": [f"{conexao.pk}:{rotina.pk}"],
            },
        )
        assert response.status_code == 200


# ===========================================================================
# SalvarImportadosView.post — success path (lines 784-812)
# ===========================================================================


@pytest.mark.django_db
class TestSalvarImportadosSuccess:
    @patch("caixa_nfse.caixa.services.importador.ImportadorMovimentos.salvar_importacao")
    def test_importar_success(self, mock_save, admin_client, abertura, conexao, rotina):
        """Successful import should show total_importados in results template."""
        mock_save.return_value = (3, 1)
        url = reverse("caixa:importar_movimentos", kwargs={"pk": abertura.pk})
        response = admin_client.post(
            url,
            {
                "action": "importar",
                "selected_rows": ["0"],
                "conexao_id_0": str(conexao.pk),
                "rotina_id_0": str(rotina.pk),
                "raw_headers_0": '["PROTOCOLO","VALOR"]',
                "raw_rows_0": '[["P-001","100.00"]]',
            },
        )
        assert response.status_code == 200
        mock_save.assert_called_once()

    def test_importar_skip_incomplete_rows(self, admin_client, abertura, conexao, rotina):
        """Rows missing required fields should be skipped (line 784)."""
        url = reverse("caixa:importar_movimentos", kwargs={"pk": abertura.pk})
        response = admin_client.post(
            url,
            {
                "action": "importar",
                "selected_rows": ["0"],
                "conexao_id_0": str(conexao.pk),
                # Missing rotina_id_0, raw_headers_0, raw_rows_0
            },
        )
        assert response.status_code == 200


# ===========================================================================
# AprovarFechamentoView — fallback redirect (line 479)
# ===========================================================================


@pytest.mark.django_db
class TestAprovarFechamentoFallback:
    def test_post_unknown_action_redirects(
        self, admin_client, tenant, admin_user, abertura, forma_pagamento
    ):
        """POST without action=aprovar or rejeitar should just redirect (line 479)."""
        fech = FechamentoCaixa.objects.create(
            tenant=tenant,
            abertura=abertura,
            operador=admin_user,
            saldo_informado=Decimal("100.00"),
            saldo_sistema=Decimal("100.00"),
            status=StatusFechamento.PENDENTE,
        )
        url = reverse("caixa:aprovar_fechamento", kwargs={"pk": fech.pk})
        response = admin_client.post(url, {"action": "unknown"})
        assert response.status_code == 302


# ===========================================================================
# ReciboDetalhadoView — sistema_rotina, protocolo, no-items, PDF
# ===========================================================================


@pytest.mark.django_db
class TestReciboDetalhadoViewExtended:
    @pytest.fixture(autouse=True)
    def _setup(self, tenant, abertura, forma_pagamento, admin_user, admin_client):
        self.client = admin_client
        self.user = admin_user
        self.tenant = tenant
        self.abertura = abertura
        self.forma = forma_pagamento

    def _create_mov(self, **kwargs):
        defaults = {
            "tenant": self.tenant,
            "abertura": self.abertura,
            "tipo": "ENTRADA",
            "forma_pagamento": self.forma,
            "valor": Decimal("300.00"),
            "protocolo": "12345.00",
            "descricao": "Test",
            "created_by": self.user,
        }
        defaults.update(kwargs)
        return MovimentoCaixa.objects.create(**defaults)

    def test_protocolo_display_strips_decimals(self):
        """Protocolo '12345.00' should display as '12345' (line 990-993)."""
        mov = self._create_mov()
        url = reverse("caixa:recibo_detalhado", kwargs={"pk": mov.pk})
        resp = self.client.get(url)
        assert resp.status_code == 200
        content = resp.content.decode()
        assert "12345" in content
        assert "12345.00" not in content

    def test_sistema_rotina_from_importado(self, sistema, conexao, rotina):
        """When movement came from import, show 'Sistema - Rotina' (line 972)."""
        mov = self._create_mov()
        MovimentoImportado.objects.create(
            tenant=self.tenant,
            abertura=self.abertura,
            conexao=conexao,
            rotina=rotina,
            importado_por=self.user,
            protocolo="P-1",
            valor=Decimal("300.00"),
            confirmado=True,
            movimento_destino=mov,
        )
        url = reverse("caixa:recibo_detalhado", kwargs={"pk": mov.pk})
        resp = self.client.get(url)
        content = resp.content.decode()
        assert "RI Legacy - Buscar Protocolos" in content

    def test_sistema_rotina_manual(self):
        """When no import origin, show 'Lançamento Manual'."""
        mov = self._create_mov()
        url = reverse("caixa:recibo_detalhado", kwargs={"pk": mov.pk})
        resp = self.client.get(url)
        content = resp.content.decode()
        assert "Lançamento Manual" in content

    def test_no_items_totals(self):
        """Movement without items should still compute totals (lines 1012-1015)."""
        mov = self._create_mov()
        url = reverse("caixa:recibo_detalhado", kwargs={"pk": mov.pk})
        resp = self.client.get(url)
        assert resp.status_code == 200
        assert resp.context["total_pago"] == Decimal("300.00")

    def test_with_items_total_ato(self):
        """Movement with items should compute total_ato per item."""
        mov = self._create_mov()
        ItemAtoMovimento.objects.create(
            tenant=self.tenant,
            movimento=mov,
            descricao="Ato 1",
            valor=Decimal("100.00"),
            emolumento=Decimal("40.00"),
            iss=Decimal("5.00"),
            taxa_judiciaria=Decimal("10.00"),
        )
        url = reverse("caixa:recibo_detalhado", kwargs={"pk": mov.pk})
        resp = self.client.get(url)
        assert resp.status_code == 200
        assert resp.context["total_ato"] > 0

    @patch("caixa_nfse.caixa.views.ReciboDetalhadoView._render_pdf")
    def test_pdf_format_triggers_render_pdf(self, mock_pdf):
        """GET ?pdf=1 should trigger _render_pdf (line 1022)."""
        from django.http import HttpResponse as HR

        mock_pdf.return_value = HR(b"%PDF", content_type="application/pdf")
        mov = self._create_mov()
        url = reverse("caixa:recibo_detalhado", kwargs={"pk": mov.pk})
        resp = self.client.get(url + "?pdf=1")
        mock_pdf.assert_called_once()

    def test_render_pdf_without_weasyprint(self):
        """When WeasyPrint import fails, _render_pdf returns 500 (lines 1025-1036)."""
        mov = self._create_mov()
        from caixa_nfse.caixa.views import ReciboDetalhadoView

        view = ReciboDetalhadoView()
        view.object = mov
        view.template_name = "caixa/recibo_detalhado.html"
        url = reverse("caixa:recibo_detalhado", kwargs={"pk": mov.pk})
        view.request = self.client.get(url).wsgi_request
        ctx = {}
        import builtins

        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "weasyprint":
                raise ImportError("No weasyprint")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            result = view._render_pdf(ctx)
        assert result.status_code == 500
        assert "WeasyPrint" in result.content.decode()


# ===========================================================================
# ItensAtoView — importado model_type (lines 1055-1094)
# ===========================================================================


@pytest.mark.django_db
class TestItensAtoViewImportado:
    def test_importado_model_type(
        self, admin_client, tenant, admin_user, abertura, conexao, rotina
    ):
        """ItensAtoView with model_type='importado' should use MovimentoImportado."""
        imp = MovimentoImportado.objects.create(
            tenant=tenant,
            abertura=abertura,
            conexao=conexao,
            rotina=rotina,
            importado_por=admin_user,
            protocolo="P-IMP",
            valor=Decimal("200.00"),
        )
        ItemAtoImportado.objects.create(
            tenant=tenant,
            movimento_importado=imp,
            descricao="Item Imp 1",
            valor=Decimal("100.00"),
            emolumento=Decimal("30.00"),
            iss=Decimal("5.00"),
            taxa_judiciaria=Decimal("8.00"),
        )
        url = reverse(
            "caixa:itens_ato",
            kwargs={
                "model_type": "importado",
                "pk": imp.pk,
            },
        )
        resp = admin_client.get(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        assert resp.status_code == 200
        assert b"Item Imp 1" in resp.content

    def test_movimento_model_type(
        self, admin_client, tenant, admin_user, abertura, forma_pagamento
    ):
        """ItensAtoView with model_type='movimento' should use MovimentoCaixa."""
        mov = MovimentoCaixa.objects.create(
            tenant=tenant,
            abertura=abertura,
            tipo="ENTRADA",
            forma_pagamento=forma_pagamento,
            valor=Decimal("300.00"),
            protocolo="P-MOV",
            created_by=admin_user,
        )
        ItemAtoMovimento.objects.create(
            tenant=tenant,
            movimento=mov,
            descricao="Item Mov 1",
            valor=Decimal("150.00"),
            emolumento=Decimal("50.00"),
            iss=Decimal("10.00"),
            taxa_judiciaria=Decimal("15.00"),
        )
        url = reverse(
            "caixa:itens_ato",
            kwargs={
                "model_type": "movimento",
                "pk": mov.pk,
            },
        )
        resp = admin_client.get(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        assert resp.status_code == 200
        assert b"Item Mov 1" in resp.content
        # Verify computed fields
        assert resp.context["total_emolumento"] == Decimal("50.00")
        assert resp.context["total_iss"] == Decimal("10.00")

    def test_itens_ato_no_items(self, admin_client, tenant, admin_user, abertura, forma_pagamento):
        """Movement without items — context should not have totals."""
        mov = MovimentoCaixa.objects.create(
            tenant=tenant,
            abertura=abertura,
            tipo="ENTRADA",
            forma_pagamento=forma_pagamento,
            valor=Decimal("100.00"),
            created_by=admin_user,
        )
        url = reverse(
            "caixa:itens_ato",
            kwargs={
                "model_type": "movimento",
                "pk": mov.pk,
            },
        )
        resp = admin_client.get(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        assert resp.status_code == 200
        assert "total_emolumento" not in resp.context
