import unittest
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from caixa_nfse.tests.factories import (
    AberturaCaixaFactory,
    CaixaFactory,
    FechamentoCaixaFactory,
    FormaPagamentoFactory,
    MovimentoCaixaFactory,
    TenantFactory,
    UserFactory,
)


@pytest.mark.django_db
class TestRelatoriosPermissions:
    def test_acesso_negado_nao_gerente(self, client):
        user = UserFactory(pode_aprovar_fechamento=False)  # Not a manager
        client.force_login(user)
        urls = [
            reverse("relatorios:index"),
            reverse("relatorios:movimentacoes"),
            reverse("relatorios:dashboard_analitico"),
        ]
        for url in urls:
            response = client.get(url)
            assert response.status_code == 403

    def test_acesso_permitido_gerente(self, client):
        user = UserFactory(pode_aprovar_fechamento=True)
        client.force_login(user)
        response = client.get(reverse("relatorios:index"))
        assert response.status_code == 200


@pytest.mark.django_db
class TestMovimentacoesReportView:
    def setup_method(self):
        from django.test import Client

        self.tenant = TenantFactory()
        self.user = UserFactory(tenant=self.tenant, pode_aprovar_fechamento=True)
        self.client = Client()
        self.client.force_login(self.user)
        self.caixa = CaixaFactory(tenant=self.tenant)
        self.abertura = AberturaCaixaFactory(caixa=self.caixa, tenant=self.tenant)
        self.movimento = MovimentoCaixaFactory(abertura=self.abertura, valor=100.00, tipo="ENTRADA")

    def test_list_movimentacoes(self):
        url = reverse("relatorios:movimentacoes")
        response = self.client.get(url)
        assert response.status_code == 200
        assert self.movimento in response.context["movimentos"]
        assert response.context["total_entradas"] == 100.00

    def test_filter_by_date(self):
        # Set explicitly explicit dates
        now = timezone.now()
        self.movimento.data_hora = now
        self.movimento.save()

        old_mov = MovimentoCaixaFactory(abertura=self.abertura, valor=50.00)
        old_mov.data_hora = now - timedelta(days=10)
        old_mov.save()

        url = reverse("relatorios:movimentacoes")
        # Ensure format matches what view expects (usually YYYY-MM-DD)
        data_inicio = now.date().isoformat()
        response = self.client.get(url, {"data_inicio": data_inicio})

        assert response.status_code == 200
        movimentos = response.context["movimentos"]
        assert self.movimento in movimentos
        assert old_mov not in movimentos

    def test_export_pdf_trigger(self):
        with unittest.mock.patch("caixa_nfse.relatorios.views.ExportService.to_pdf") as mock_pdf:
            mock_pdf.return_value = b"PDF_RESPONSE"
            url = reverse("relatorios:movimentacoes")
            response = self.client.get(url, {"export": "pdf"})
            mock_pdf.assert_called_once()
            assert response.content == b"PDF_RESPONSE"


@pytest.mark.django_db
class TestResumoCaixaReportView:
    def setup_method(self):
        from django.test import Client

        self.tenant = TenantFactory()
        self.user = UserFactory(tenant=self.tenant, pode_aprovar_fechamento=True)
        self.client = Client()
        self.client.force_login(self.user)
        self.caixa = CaixaFactory(tenant=self.tenant)
        self.abertura = AberturaCaixaFactory(
            caixa=self.caixa, tenant=self.tenant, saldo_abertura=100
        )
        # Create movements to affect totals
        MovimentoCaixaFactory(abertura=self.abertura, valor=50, tipo="ENTRADA")
        MovimentoCaixaFactory(abertura=self.abertura, valor=20, tipo="SAIDA")

    def test_resumo_calculo(self):
        url = reverse("relatorios:resumo_caixa")
        response = self.client.get(url)
        assert response.status_code == 200
        resumos = response.context["resumos"]
        assert len(resumos) == 1
        r = resumos[0]
        assert r["entradas"] == 50
        assert r["saidas"] == 20
        assert r["saldo_final"] == 100 + 50 - 20  # 130


@pytest.mark.django_db
class TestDashboardAnaliticoView:
    def setup_method(self):
        from django.test import Client

        self.tenant = TenantFactory()
        self.user = UserFactory(tenant=self.tenant, pode_aprovar_fechamento=True)
        self.client = Client()
        self.client.force_login(self.user)
        self.caixa = CaixaFactory(tenant=self.tenant)
        self.abertura = AberturaCaixaFactory(caixa=self.caixa, tenant=self.tenant)
        MovimentoCaixaFactory(abertura=self.abertura, valor=100, tipo="ENTRADA")


@pytest.mark.django_db
class TestOtherReports:
    def setup_method(self):
        from django.test import Client

        self.tenant = TenantFactory()
        self.user = UserFactory(tenant=self.tenant, pode_aprovar_fechamento=True)
        self.client = Client()
        self.client.force_login(self.user)
        self.caixa = CaixaFactory(tenant=self.tenant)
        self.abertura = AberturaCaixaFactory(caixa=self.caixa, tenant=self.tenant)
        self.movimento = MovimentoCaixaFactory(abertura=self.abertura, valor=100, tipo="ENTRADA")

    def test_formas_pagamento(self):
        fp = FormaPagamentoFactory(tenant=self.tenant, nome="Pix")
        self.movimento.forma_pagamento = fp
        self.movimento.save()

        url = reverse("relatorios:formas_pagamento")
        response = self.client.get(url)
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert "Pix" in content

    def test_performance_operador(self):
        url = reverse("relatorios:performance_operador")
        response = self.client.get(url)
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        # Verifica user.first_name em vez de email, pois pode ser o que aparece na tela
        assert self.user.first_name in content

    def test_historico_aberturas(self):
        url = reverse("relatorios:historico_aberturas")
        response = self.client.get(url)
        assert response.status_code == 200
        assert self.abertura in response.context["aberturas"]

    def test_diferencas_caixa(self):
        fechamento = FechamentoCaixaFactory(
            abertura=self.abertura,
            operador=self.user,
            saldo_sistema=100,
            saldo_informado=90,
            diferenca=-10,
            status="FECHADO",  # Ensure status is valid
        )
        url = reverse("relatorios:diferencas_caixa")
        response = self.client.get(url)
        assert response.status_code == 200
        assert fechamento in response.context["fechamentos"]

    def test_log_acoes(self):
        from caixa_nfse.auditoria.models import RegistroAuditoria

        log = RegistroAuditoria.objects.create(
            tenant=self.tenant, usuario=self.user, acao="LOGIN", tabela="User"
        )
        url = reverse("relatorios:log_acoes")
        response = self.client.get(url)
        assert response.status_code == 200
        assert log in response.context["registros"]

    def test_fechamentos_pendentes(self):
        fechamento = FechamentoCaixaFactory(
            abertura=self.abertura, operador=self.user, status="PENDENTE"
        )
        url = reverse("relatorios:fechamentos_pendentes")
        response = self.client.get(url)
        assert response.status_code == 200
        assert fechamento in response.context["fechamentos"]

    def test_dashboard_context(self):
        url = reverse("relatorios:dashboard_analitico")
        response = self.client.get(url)
        assert response.status_code == 200
        assert response.context["total_entradas"] == 100
        assert "chart_labels" in response.context
