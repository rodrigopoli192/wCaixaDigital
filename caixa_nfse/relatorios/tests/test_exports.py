import unittest

import pytest
from django.urls import reverse

from caixa_nfse.tests.factories import (
    AberturaCaixaFactory,
    CaixaFactory,
    FechamentoCaixaFactory,
    FormaPagamentoFactory,
    MovimentoCaixaFactory,
    RegistroAuditoriaFactory,
    TenantFactory,
    UserFactory,
)


@pytest.mark.django_db
class TestAllExports:
    def setup_method(self):
        from django.test import Client

        self.tenant = TenantFactory()
        self.user = UserFactory(tenant=self.tenant, pode_aprovar_fechamento=True)
        self.client = Client()
        self.client.force_login(self.user)
        self.caixa = CaixaFactory(tenant=self.tenant)
        self.abertura = AberturaCaixaFactory(caixa=self.caixa, tenant=self.tenant)

        # Create Data for all reports
        # Movimentacoes / Formas Pagamento / Performance / Dashboard
        self.fp = FormaPagamentoFactory(tenant=self.tenant, nome="Dinheiro")
        self.movimento = MovimentoCaixaFactory(
            abertura=self.abertura, valor=100.00, tipo="ENTRADA", forma_pagamento=self.fp
        )

        # Fechamento / Diferencas / Pendentes
        self.fechamento = FechamentoCaixaFactory(
            abertura=self.abertura,
            operador=self.user,
            saldo_sistema=100,
            saldo_informado=100,
            status="FECHADO",
        )

        # Log Acoes
        self.log = RegistroAuditoriaFactory(
            tenant=self.tenant, usuario=self.user, acao="CREATE", tabela="TestTable"
        )

    @pytest.mark.parametrize(
        "view_name",
        [
            "relatorios:movimentacoes",
            "relatorios:resumo_caixa",
            "relatorios:formas_pagamento",
            "relatorios:performance_operador",
            "relatorios:historico_aberturas",
            "relatorios:diferencas_caixa",
            "relatorios:log_acoes",
        ],
    )
    def test_export_pdf_mocked(self, view_name):
        url = reverse(view_name)
        with unittest.mock.patch("caixa_nfse.relatorios.views.ExportService.to_pdf") as mock_pdf:
            mock_pdf.return_value = "PDF_CONTENT"
            self.client.get(url, {"export": "pdf"})
            assert mock_pdf.called
            # Ensure get_export_data was called by checking call args if possible,
            # or just rely on coverage.
            # We can verify that data was passed to to_pdf
            call_kwargs = mock_pdf.call_args[1]
            rows = call_kwargs.get("rows", [])
            assert len(rows) > 0, f"No rows exported for {view_name}"

    @pytest.mark.parametrize(
        "view_name",
        [
            "relatorios:movimentacoes",
            "relatorios:resumo_caixa",
            "relatorios:formas_pagamento",
            "relatorios:performance_operador",
            "relatorios:historico_aberturas",
            "relatorios:diferencas_caixa",
            "relatorios:log_acoes",
        ],
    )
    def test_export_xlsx_mocked(self, view_name):
        url = reverse(view_name)
        with unittest.mock.patch("caixa_nfse.relatorios.views.ExportService.to_xlsx") as mock_xlsx:
            mock_xlsx.return_value = "XLSX_CONTENT"
            self.client.get(url, {"export": "xlsx"})
            assert mock_xlsx.called
            call_kwargs = mock_xlsx.call_args[1]
            rows = call_kwargs.get("rows", [])
            assert len(rows) > 0, f"No rows exported for {view_name}"
