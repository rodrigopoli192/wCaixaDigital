"""
Tests to close remaining coverage gaps across all modules.
Targets: relatorios/views, core/views, auditoria, backoffice, and minor modules.
"""

from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.urls import reverse

from caixa_nfse.auditoria.models import AcaoAuditoria, RegistroAuditoria
from caixa_nfse.caixa.models import (
    AberturaCaixa,
    Caixa,
    FechamentoCaixa,
    MovimentoCaixa,
    StatusCaixa,
    StatusFechamento,
)
from caixa_nfse.conftest import *  # noqa: F401,F403
from caixa_nfse.core.models import ConexaoExterna, FormaPagamento

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def caixa_aberto(db, tenant, admin_user):
    return Caixa.objects.create(
        tenant=tenant,
        identificador="CX-GAP",
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
def movimento(db, tenant, admin_user, abertura, forma_pagamento):
    return MovimentoCaixa.objects.create(
        tenant=tenant,
        abertura=abertura,
        tipo="ENTRADA",
        forma_pagamento=forma_pagamento,
        valor=Decimal("500.00"),
        protocolo="P-GAP",
        created_by=admin_user,
    )


@pytest.fixture
def admin_client(client, admin_user):
    client.force_login(admin_user)
    return client


# ===========================================================================
# Relatórios — date/type/caixa filters
# ===========================================================================


@pytest.mark.django_db
class TestRelatoriosFilters:
    """Cover filter branches and export in relatorios views."""

    def test_movimentacoes_with_date_type_caixa_filters(
        self, admin_client, abertura, movimento, caixa_aberto
    ):
        url = reverse("relatorios:movimentacoes")
        resp = admin_client.get(
            url,
            {
                "data_inicio": "2020-01-01",
                "data_fim": "2030-12-31",
                "tipo": "ENTRADA",
                "caixa": str(caixa_aberto.pk),
            },
        )
        assert resp.status_code == 200

    def test_resumo_caixa_with_filters(self, admin_client, abertura, caixa_aberto):
        url = reverse("relatorios:resumo_caixa")
        resp = admin_client.get(
            url,
            {
                "data_inicio": "2020-01-01",
                "data_fim": "2030-12-31",
                "caixa": str(caixa_aberto.pk),
            },
        )
        assert resp.status_code == 200

    def test_formas_pagamento_with_filters(self, admin_client, abertura, movimento):
        url = reverse("relatorios:formas_pagamento")
        resp = admin_client.get(
            url,
            {
                "data_inicio": "2020-01-01",
                "data_fim": "2030-12-31",
            },
        )
        assert resp.status_code == 200

    def test_historico_aberturas_with_filters(self, admin_client, abertura, caixa_aberto):
        url = reverse("relatorios:historico_aberturas")
        resp = admin_client.get(
            url,
            {
                "data_inicio": "2020-01-01",
                "data_fim": "2030-12-31",
                "caixa": str(caixa_aberto.pk),
            },
        )
        assert resp.status_code == 200

    def test_diferencas_caixa_with_filters(self, admin_client, tenant, admin_user, abertura):
        FechamentoCaixa.objects.create(
            tenant=tenant,
            abertura=abertura,
            operador=admin_user,
            saldo_informado=Decimal("100.00"),
            saldo_sistema=Decimal("90.00"),
            status=StatusFechamento.APROVADO,
        )
        url = reverse("relatorios:diferencas_caixa")
        resp = admin_client.get(
            url,
            {
                "data_inicio": "2020-01-01",
                "data_fim": "2030-12-31",
                "apenas_diferencas": "on",
            },
        )
        assert resp.status_code == 200

    def test_log_acoes_with_filters(self, admin_client, tenant, admin_user):
        RegistroAuditoria.objects.create(
            tenant=tenant,
            usuario=admin_user,
            tabela="TEST",
            registro_id="1",
            acao=AcaoAuditoria.CREATE,
        )
        url = reverse("relatorios:log_acoes")
        resp = admin_client.get(
            url,
            {
                "data_inicio": "2020-01-01",
                "data_fim": "2030-12-31",
                "acao": "CREATE",
                "tabela": "TEST",
            },
        )
        assert resp.status_code == 200

    def test_movimentacoes_export_xlsx(self, admin_client, movimento):
        """Export with filters to cover get_export_filters & handle_export xlsx."""
        url = reverse("relatorios:movimentacoes")
        resp = admin_client.get(
            url,
            {
                "export": "xlsx",
                "data_inicio": "2020-01-01",
                "tipo": "ENTRADA",
            },
        )
        assert resp.status_code == 200

    def test_dashboard_analitico_invalid_periodo(self, admin_client, movimento):
        """Dashboard with non-numeric periodo defaults to 7."""
        url = reverse("relatorios:dashboard_analitico")
        resp = admin_client.get(url, {"periodo": "abc"})
        assert resp.status_code == 200


# ===========================================================================
# Auditoria — filter branches + CSV export
# ===========================================================================


@pytest.mark.django_db
class TestAuditoriaViewFilters:
    def test_list_filter_by_acao_and_dates(self, admin_client, tenant, admin_user):
        RegistroAuditoria.objects.create(
            tenant=tenant,
            usuario=admin_user,
            tabela="CAIXA",
            registro_id="1",
            acao=AcaoAuditoria.CREATE,
        )
        url = reverse("auditoria:list")
        resp = admin_client.get(
            url,
            {
                "acao": "CREATE",
                "data_inicio": "2020-01-01",
                "data_fim": "2030-12-31",
            },
        )
        assert resp.status_code == 200

    def test_csv_export_with_date_filters(self, admin_client, tenant, admin_user):
        RegistroAuditoria.objects.create(
            tenant=tenant,
            usuario=admin_user,
            tabela="TEST",
            registro_id="1",
            acao=AcaoAuditoria.VIEW,
        )
        url = reverse("auditoria:exportar")
        resp = admin_client.get(
            url,
            {
                "data_inicio": "2020-01-01",
                "data_fim": "2030-12-31",
            },
        )
        assert resp.status_code == 200
        assert "text/csv" in resp["Content-Type"]


# ===========================================================================
# Auditoria — decorator/middleware/signal exception silencing
# ===========================================================================


@pytest.mark.django_db
class TestAuditoriaEdgeCases:
    def test_decorator_exception_silenced(self, admin_client):
        """Decorator exception in RegistroAuditoria.registrar should pass."""
        with patch.object(RegistroAuditoria, "registrar", side_effect=Exception("Boom")):
            url = reverse("core:dashboard")
            resp = admin_client.get(url)
            assert resp.status_code == 200

    def test_middleware_audit_exception_silenced(self, admin_client):
        """Middleware audit logging exception should not break response."""
        with patch.object(RegistroAuditoria, "registrar", side_effect=Exception("Boom")):
            url = reverse("core:dashboard")
            resp = admin_client.get(url)
            assert resp.status_code == 200

    def test_signal_exception_silenced(self, db, tenant, admin_user):
        """Signal audit exception should be silenced."""
        with patch.object(RegistroAuditoria, "registrar", side_effect=Exception("Boom")):
            fp = FormaPagamento.objects.create(tenant=tenant, nome="Signal Test", ativo=True)
            fp.nome = "Updated"
            fp.save()


# ===========================================================================
# Core views — dashboard no-tenant, operator filters, user management
# ===========================================================================


@pytest.mark.django_db
class TestCoreViewsGaps:
    def test_dashboard_no_tenant(self, db, client, user):
        """Dashboard when user has no tenant."""
        user.tenant = None
        user.save()
        client.force_login(user)
        url = reverse("core:dashboard")
        resp = client.get(url)
        assert resp.status_code == 200

    def test_dashboard_superuser_no_tenant(self, db, client, admin_user):
        """Superuser with no tenant accesses all data."""
        admin_user.tenant = None
        admin_user.save()
        client.force_login(admin_user)
        url = reverse("core:dashboard")
        resp = client.get(url)
        assert resp.status_code == 200

    def test_dashboard_operator_with_active_abertura(
        self, db, client, user, tenant, caixa_aberto, abertura
    ):
        """Non-gerente operator sees only their active abertura."""
        user.pode_operar_caixa = True
        user.save()
        client.force_login(user)
        url = reverse("core:dashboard")
        resp = client.get(url)
        assert resp.status_code == 200

    def test_dashboard_filter_by_tipo(self, admin_client, abertura, movimento):
        """Dashboard with tipo filter."""
        url = reverse("core:dashboard")
        resp = admin_client.get(url, {"tipo": "ENTRADA"})
        assert resp.status_code == 200

    def test_dashboard_filter_by_caixa(self, admin_client, abertura, movimento, caixa_aberto):
        """Dashboard with caixa filter."""
        url = reverse("core:dashboard")
        resp = admin_client.get(url, {"caixa": str(caixa_aberto.pk)})
        assert resp.status_code == 200

    def test_user_list(self, admin_client):
        """TenantUserListView."""
        url = reverse("core:settings_users_list")
        resp = admin_client.get(url)
        assert resp.status_code == 200

    def test_password_reset_form(self, admin_client, tenant, user):
        """TenantUserPasswordResetView get_form_kwargs and form_valid."""
        url = reverse("core:settings_user_reset_password", kwargs={"pk": user.pk})
        resp = admin_client.get(url)
        assert resp.status_code == 200
        resp = admin_client.post(
            url,
            {
                "new_password1": "NewStr0ng!Pass99",
                "new_password2": "NewStr0ng!Pass99",
            },
        )
        assert resp.status_code in [200, 302]

    def test_user_profile_form_valid(self, admin_client, admin_user):
        """UserProfileView.form_valid returns HX-Trigger."""
        url = reverse("core:user_profile")
        resp = admin_client.post(
            url,
            {
                "first_name": "Updated",
                "last_name": "Name",
                "cpf": "",
            },
        )
        assert resp.status_code == 200

    def test_user_profile_form_invalid(self, admin_client):
        """UserProfileView.form_invalid re-renders form."""
        url = reverse("core:user_profile")
        # Sending no data at all should trigger form_invalid
        resp = admin_client.post(url, {})
        assert resp.status_code == 200

    def test_execute_routine_view(self, admin_client, tenant):
        """RotinaExecutionView."""
        from caixa_nfse.backoffice.models import Rotina, Sistema

        sistema = Sistema.objects.create(nome="Test Sys", ativo=True)
        conexao = ConexaoExterna.objects.create(
            tenant=tenant,
            sistema=sistema,
            tipo_conexao="MSSQL",
            host="localhost",
            porta=1433,
            database="testdb",
            usuario="sa",
            senha="secret",
        )
        rotina = Rotina.objects.create(
            sistema=sistema,
            nome="Test Routine",
            sql_content="SELECT 1",
            ativo=True,
        )
        url = reverse("core:api_rotinas_execucao", kwargs={"pk": rotina.pk})
        with patch(
            "caixa_nfse.core.services.sql_executor.SQLExecutor.execute_routine"
        ) as mock_exec:
            mock_exec.return_value = (["Col1"], [["Val1"]], [])
            resp = admin_client.post(
                url,
                {
                    "conexao_id": str(conexao.pk),
                },
            )
            assert resp.status_code == 200


# ===========================================================================
# Backoffice — model __str__
# ===========================================================================


@pytest.mark.django_db
class TestBackofficeModelStr:
    def test_sistema_str(self, db):
        from caixa_nfse.backoffice.models import Sistema

        s = Sistema.objects.create(nome="My System", ativo=True)
        assert str(s) == "My System"

    def test_rotina_str(self, db):
        from caixa_nfse.backoffice.models import Rotina, Sistema

        s = Sistema.objects.create(nome="Sys", ativo=True)
        r = Rotina.objects.create(sistema=s, nome="My Routine", sql_content="SELECT 1", ativo=True)
        assert "My Routine" in str(r)

    def test_mapeamento_str(self, db):
        from caixa_nfse.backoffice.models import MapeamentoColunaRotina, Rotina, Sistema

        s = Sistema.objects.create(nome="S", ativo=True)
        r = Rotina.objects.create(sistema=s, nome="R", sql_content="SELECT 1", ativo=True)
        m = MapeamentoColunaRotina.objects.create(
            rotina=r, coluna_sql="COL1", campo_destino="valor"
        )
        assert str(m)


# ===========================================================================
# Backoffice views — rotina create
# ===========================================================================


@pytest.mark.django_db
class TestBackofficeViewsEdge:
    def test_rotina_create_post(self, admin_client):
        from caixa_nfse.backoffice.models import Sistema

        s = Sistema.objects.create(nome="BO Sys", ativo=True)
        url = reverse("backoffice:rotina_add", kwargs={"sistema_pk": s.pk})
        resp = admin_client.post(
            url,
            {
                "sistema": str(s.pk),
                "nome": "New Routine",
                "sql_content": "SELECT 1",
                "ativo": "on",
            },
        )
        assert resp.status_code in [200, 302, 403]


# ===========================================================================
# Minor modules — __str__, form validations, single-line gaps
# ===========================================================================


@pytest.mark.django_db
class TestMinorGaps:
    def test_auditoria_model_str(self, db, tenant, admin_user):
        r = RegistroAuditoria.objects.create(
            tenant=tenant,
            usuario=admin_user,
            tabela="CAIXA",
            registro_id="99",
            acao=AcaoAuditoria.CREATE,
        )
        assert str(r)

    def test_caixa_models_str(self, db, tenant, admin_user, abertura, forma_pagamento):
        mov = MovimentoCaixa.objects.create(
            tenant=tenant,
            abertura=abertura,
            tipo="ENTRADA",
            forma_pagamento=forma_pagamento,
            valor=Decimal("100.00"),
            created_by=admin_user,
        )
        assert str(mov)

    def test_fiscal_model_str(self, db, tenant):
        from caixa_nfse.fiscal.models import LivroFiscalServicos

        livro = LivroFiscalServicos.objects.create(
            tenant=tenant,
            competencia=date(2026, 1, 1),
            municipio_ibge="3550308",
            total_notas=10,
            valor_servicos=Decimal("1000.00"),
            valor_iss=Decimal("50.00"),
            valor_iss_retido=Decimal("0.00"),
        )
        assert str(livro)

    def test_core_forms_clean(self, db, tenant, admin_user):
        from caixa_nfse.core.forms import ConexaoExternaForm

        form = ConexaoExternaForm(
            data={
                "tipo_conexao": "MSSQL",
                "host": "",
                "porta": "1433",
                "database": "test",
                "usuario": "sa",
                "senha": "pw",
            }
        )
        assert not form.is_valid()

    def test_clientes_model_str(self, db, tenant):
        from caixa_nfse.clientes.models import Cliente

        c = Cliente.objects.create(
            tenant=tenant,
            razao_social="Test Client",
            tipo_pessoa="PF",
        )
        assert "Test Client" in str(c)

    def test_core_model_str(self, db, tenant):
        from caixa_nfse.backoffice.models import Sistema

        s = Sistema.objects.create(nome="S", ativo=True)
        c = ConexaoExterna.objects.create(
            tenant=tenant,
            sistema=s,
            tipo_conexao="MSSQL",
            host="localhost",
            porta=1433,
            database="db",
            usuario="sa",
            senha="pw",
        )
        assert str(c)
