"""
Tests for Caixa import-related views:
ImportarMovimentosView, ListaImportadosView, ConfirmarImportadosView, ExcluirImportadosView.

Covers caixa/views.py lines: 477-514, 530-531, 536-540, 558-562, 739-744,
761-765, 817-852, 855-905, 908-944.
"""

from decimal import Decimal
from unittest.mock import patch

import pytest
from django.urls import reverse

from caixa_nfse.backoffice.models import Rotina, Sistema
from caixa_nfse.caixa.models import (
    AberturaCaixa,
    Caixa,
    MovimentoImportado,
    StatusCaixa,
)
from caixa_nfse.conftest import *  # noqa: F401,F403
from caixa_nfse.core.models import ConexaoExterna, FormaPagamento

# ---------------------------------------------------------------------------
# Fixtures
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
    caixa = Caixa.objects.create(
        tenant=tenant,
        identificador="CX-IMP",
        tipo="FISICO",
        status=StatusCaixa.ABERTO,
        operador_atual=admin_user,
        saldo_atual=Decimal("100.00"),
    )
    return caixa


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
    return FormaPagamento.objects.create(
        tenant=tenant,
        nome="Dinheiro",
        ativo=True,
    )


@pytest.fixture
def importado(db, tenant, abertura, conexao, rotina, admin_user):
    return MovimentoImportado.objects.create(
        tenant=tenant,
        abertura=abertura,
        conexao=conexao,
        rotina=rotina,
        importado_por=admin_user,
        protocolo="P-001",
        valor=Decimal("50.00"),
        descricao="Registro Importado",
    )


@pytest.fixture
def admin_client(client, admin_user):
    client.force_login(admin_user)
    return client


# ===========================================================================
# ImportarMovimentosView
# ===========================================================================


@pytest.mark.django_db
class TestImportarMovimentosView:
    def test_get_form(self, admin_client, abertura, conexao, rotina):
        conexao.rotinas.add(rotina)
        url = reverse("caixa:importar_movimentos", kwargs={"pk": abertura.pk})
        response = admin_client.get(url)
        assert response.status_code == 200
        assert "abertura" in response.context
        assert "conexoes_tree" in response.context

    def test_post_no_pairs(self, admin_client, abertura):
        url = reverse("caixa:importar_movimentos", kwargs={"pk": abertura.pk})
        response = admin_client.post(url, {"action": "buscar"})
        assert response.status_code == 200
        assert "Selecione ao menos uma" in response.content.decode()

    def test_post_invalid_pairs_format(self, admin_client, abertura):
        url = reverse("caixa:importar_movimentos", kwargs={"pk": abertura.pk})
        response = admin_client.post(
            url,
            {
                "action": "buscar",
                "conexao_rotina_pairs": ["invalid_no_colon"],
            },
        )
        assert response.status_code == 200
        assert "Selecione ao menos uma" in response.content.decode()

    @patch("caixa_nfse.caixa.services.importador.ImportadorMovimentos.executar_rotinas")
    def test_post_buscar_exception(self, mock_exec, admin_client, abertura, conexao, rotina):
        mock_exec.side_effect = Exception("DB connection failed")
        url = reverse("caixa:importar_movimentos", kwargs={"pk": abertura.pk})
        response = admin_client.post(
            url,
            {
                "action": "buscar",
                "conexao_rotina_pairs": [f"{conexao.pk}:{rotina.pk}"],
            },
        )
        assert response.status_code == 200
        assert "Erro ao conectar" in response.content.decode()

    def test_post_importar_no_selection(self, admin_client, abertura):
        url = reverse("caixa:importar_movimentos", kwargs={"pk": abertura.pk})
        response = admin_client.post(url, {"action": "importar"})
        assert response.status_code == 200
        assert "Nenhum item selecionado" in response.content.decode()

    @patch("caixa_nfse.caixa.services.importador.ImportadorMovimentos.salvar_importacao")
    def test_post_importar_exception(self, mock_save, admin_client, abertura, conexao, rotina):
        mock_save.side_effect = Exception("Save failed")
        url = reverse("caixa:importar_movimentos", kwargs={"pk": abertura.pk})
        response = admin_client.post(
            url,
            {
                "action": "importar",
                "selected_rows": ["0"],
                "conexao_id_0": str(conexao.pk),
                "rotina_id_0": str(rotina.pk),
                "raw_headers_0": '["col1"]',
                "raw_rows_0": '[["val1"]]',
            },
        )
        assert response.status_code == 200
        assert "Erro ao importar" in response.content.decode()


# ===========================================================================
# ListaImportadosView
# ===========================================================================


@pytest.mark.django_db
class TestListaImportadosView:
    def test_list_importados(self, admin_client, abertura, importado, forma_pagamento):
        url = reverse("caixa:lista_importados", kwargs={"pk": abertura.pk})
        response = admin_client.get(url)
        assert response.status_code == 200
        assert "importados" in response.context
        assert "formas_pagamento" in response.context
        assert len(response.context["importados"]) == 1

    def test_htmx_template(self, admin_client, abertura, importado, forma_pagamento):
        url = reverse("caixa:lista_importados", kwargs={"pk": abertura.pk})
        response = admin_client.get(url, HTTP_HX_REQUEST="true")
        assert response.status_code == 200

    def test_empty_list(self, admin_client, abertura, forma_pagamento):
        url = reverse("caixa:lista_importados", kwargs={"pk": abertura.pk})
        response = admin_client.get(url)
        assert response.status_code == 200
        assert len(response.context["importados"]) == 0


# ===========================================================================
# ConfirmarImportadosView
# ===========================================================================


@pytest.mark.django_db
class TestConfirmarImportadosView:
    def test_post_no_ids(self, admin_client, abertura):
        url = reverse("caixa:confirmar_importados", kwargs={"pk": abertura.pk})
        response = admin_client.post(url, {})
        assert response.status_code == 200
        assert "Selecione ao menos um" in response.content.decode()

    def test_post_no_forma_pagamento(self, admin_client, abertura, importado):
        url = reverse("caixa:confirmar_importados", kwargs={"pk": abertura.pk})
        response = admin_client.post(
            url,
            {"importado_ids": [str(importado.pk)]},
        )
        assert response.status_code == 200
        assert "Selecione ao menos um" in response.content.decode()

    @patch("caixa_nfse.caixa.services.importador.ImportadorMovimentos.confirmar_movimentos")
    def test_post_success(self, mock_confirm, admin_client, abertura, importado, forma_pagamento):
        mock_confirm.return_value = 1
        url = reverse("caixa:confirmar_importados", kwargs={"pk": abertura.pk})
        response = admin_client.post(
            url,
            {
                "importado_ids": [str(importado.pk)],
                "forma_pagamento_id": str(forma_pagamento.pk),
                "tipo": "ENTRADA",
            },
        )
        assert response.status_code == 200
        assert response["HX-Refresh"] == "true"
        mock_confirm.assert_called_once()

    @patch("caixa_nfse.caixa.services.importador.ImportadorMovimentos.confirmar_movimentos")
    def test_post_exception(self, mock_confirm, admin_client, abertura, importado, forma_pagamento):
        mock_confirm.side_effect = Exception("Confirm failed")
        url = reverse("caixa:confirmar_importados", kwargs={"pk": abertura.pk})
        response = admin_client.post(
            url,
            {
                "importado_ids": [str(importado.pk)],
                "forma_pagamento_id": str(forma_pagamento.pk),
                "tipo": "ENTRADA",
            },
        )
        assert response.status_code == 200
        assert "Erro ao confirmar" in response.content.decode()


# ===========================================================================
# ExcluirImportadosView
# ===========================================================================


@pytest.mark.django_db
class TestExcluirImportadosView:
    def test_post_no_ids(self, admin_client, abertura):
        url = reverse("caixa:excluir_importados", kwargs={"pk": abertura.pk})
        response = admin_client.post(url, {})
        assert response.status_code == 200
        assert "Selecione ao menos um" in response.content.decode()

    def test_post_delete_success(self, admin_client, abertura, importado):
        url = reverse("caixa:excluir_importados", kwargs={"pk": abertura.pk})
        response = admin_client.post(
            url,
            {"importado_ids": [str(importado.pk)]},
        )
        assert response.status_code == 200
        assert response["HX-Refresh"] == "true"
        assert not MovimentoImportado.objects.filter(pk=importado.pk).exists()

    def test_post_confirmed_not_deleted(self, admin_client, abertura, importado):
        importado.confirmado = True
        importado.save()
        url = reverse("caixa:excluir_importados", kwargs={"pk": abertura.pk})
        response = admin_client.post(
            url,
            {"importado_ids": [str(importado.pk)]},
        )
        assert response.status_code == 200
        # Confirmed items should not be deleted by filter(confirmado=False)
        assert MovimentoImportado.objects.filter(pk=importado.pk).exists()

    def test_post_wrong_tenant(self, client, abertura, importado, tenant):
        from caixa_nfse.core.models import Tenant, User

        other_tenant = Tenant.objects.create(
            razao_social="Outra",
            cnpj="98765432000199",
            logradouro="R",
            numero="1",
            bairro="B",
            cidade="C",
            uf="SP",
            cep="00000000",
        )
        other_user = User.objects.create_user(
            email="other@test.com",
            password="pass123",
            tenant=other_tenant,
            pode_operar_caixa=True,
        )
        client.force_login(other_user)
        # This abertura belongs to a different tenant so get_object() should 404
        url = reverse("caixa:excluir_importados", kwargs={"pk": abertura.pk})
        response = client.post(url, {"importado_ids": [str(importado.pk)]})
        assert response.status_code == 404
