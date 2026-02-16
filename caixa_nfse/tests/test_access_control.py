"""
Access Control Tests — validate URL access for each user profile.

Profiles:
- Platform Admin (superuser, no tenant)
- Tenant Admin (gerente — pode_aprovar_fechamento, pode_emitir_nfse)
- Tenant User (operador — pode_operar_caixa only)
- Unauthenticated
"""

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from caixa_nfse.caixa.models import Caixa
from caixa_nfse.core.models import Tenant

User = get_user_model()

# Disable whitenoise and staticfiles for speed
TEST_STATICFILES = []


@override_settings(STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage")
class AccessTestBase(TestCase):
    """Base class with fixtures for all access tests."""

    @classmethod
    def setUpTestData(cls):
        # Tenant
        cls.tenant = Tenant.objects.create(
            razao_social="Cartório 1 Teste",
            nome_fantasia="Cartório 1",
            cnpj="12345678000199",
            inscricao_municipal="123456",
            email="contato@cartorio1.com",
            telefone="11999999999",
            logradouro="Rua Teste",
            numero="100",
            bairro="Centro",
            cidade="São Paulo",
            uf="SP",
            cep="01001000",
        )

        # Platform Admin (superuser, no tenant)
        cls.platform_admin = User.objects.create_superuser(
            email="admin@caixadigital.com",
            password="admin123",
            first_name="Admin",
            last_name="Plataforma",
        )

        # Tenant Admin (gerente)
        cls.tenant_admin = User.objects.create_user(
            email="gerente@cartorio1.com",
            password="123456",
            first_name="Gerente",
            last_name="Teste",
            tenant=cls.tenant,
            pode_operar_caixa=True,
            pode_aprovar_fechamento=True,
            pode_emitir_nfse=True,
            pode_cancelar_nfse=True,
            pode_exportar_dados=True,
        )

        # Tenant User (operador)
        cls.tenant_user = User.objects.create_user(
            email="caixa@cartorio1.com",
            password="senhas123",
            first_name="Caixa",
            last_name="Operador",
            tenant=cls.tenant,
            pode_operar_caixa=True,
            pode_aprovar_fechamento=False,
            pode_emitir_nfse=False,
            pode_cancelar_nfse=False,
            pode_exportar_dados=False,
        )

        # Caixa for detail/operation URLs
        cls.caixa = Caixa.objects.create(
            tenant=cls.tenant,
            identificador="CAIXA-TEST-01",
            tipo="FISICO",
        )


# ── BACKOFFICE (Platform Admin) ─────────────────────────────


class TestPlatformAdminAccess(AccessTestBase):
    """Platform admin should access /platform/* and be blocked from tenant pages."""

    BACKOFFICE_URLS = [
        "/platform/",
        "/platform/tenants/new/",
        "/platform/sistemas/",
        "/platform/sistemas/new/",
    ]

    def test_backoffice_accessible_for_superuser(self):
        self.client.force_login(self.platform_admin)
        for url in self.BACKOFFICE_URLS:
            resp = self.client.get(url)
            self.assertIn(
                resp.status_code,
                [200, 302],
                f"Platform admin should access {url}, got {resp.status_code}",
            )

    def test_backoffice_blocked_for_tenant_admin(self):
        self.client.force_login(self.tenant_admin)
        for url in self.BACKOFFICE_URLS:
            resp = self.client.get(url)
            self.assertIn(
                resp.status_code,
                [302, 403],
                f"Tenant admin should NOT access {url}, got {resp.status_code}",
            )

    def test_backoffice_blocked_for_tenant_user(self):
        self.client.force_login(self.tenant_user)
        for url in self.BACKOFFICE_URLS:
            resp = self.client.get(url)
            self.assertIn(
                resp.status_code,
                [302, 403],
                f"Tenant user should NOT access {url}, got {resp.status_code}",
            )


# ── CORE (Dashboard, Profile) ────────────────────────────────


class TestCoreAccess(AccessTestBase):
    """Dashboard and profile are accessible to all authenticated users."""

    ALL_USER_URLS = [
        "/",  # Dashboard
        "/perfil/",  # User profile
        "/health/",  # Health check (no auth)
    ]

    def test_dashboard_accessible_for_all_authenticated(self):
        for user in [self.platform_admin, self.tenant_admin, self.tenant_user]:
            self.client.force_login(user)
            for url in self.ALL_USER_URLS:
                resp = self.client.get(url)
                self.assertIn(
                    resp.status_code,
                    [200, 302],
                    f"{user.email} should access {url}, got {resp.status_code}",
                )

    def test_health_check_no_auth_required(self):
        resp = self.client.get("/health/")
        self.assertEqual(resp.status_code, 200)


# ── SETTINGS (Tenant Admin Only) ─────────────────────────────


class TestSettingsAccess(AccessTestBase):
    """Settings pages require TenantAdminRequiredMixin (pode_aprovar_fechamento)."""

    ADMIN_ONLY_URLS = [
        "/settings/",
        "/settings/users/",
        "/settings/users/add/",
        "/settings/parametros/",
        "/settings/nfse/",
        "/settings/formas-pagamento/",
        "/settings/formas-pagamento/add/",
        "/settings/conexoes/",
        "/settings/conexoes/add/",
    ]

    def test_settings_accessible_for_tenant_admin(self):
        self.client.force_login(self.tenant_admin)
        for url in self.ADMIN_ONLY_URLS:
            resp = self.client.get(url)
            self.assertIn(
                resp.status_code,
                [200, 302],
                f"Tenant admin should access {url}, got {resp.status_code}",
            )

    def test_settings_blocked_for_tenant_user(self):
        self.client.force_login(self.tenant_user)
        for url in self.ADMIN_ONLY_URLS:
            resp = self.client.get(url)
            self.assertIn(
                resp.status_code,
                [302, 403],
                f"Tenant user should NOT access {url}, got {resp.status_code}",
            )


# ── CAIXA (Tenant Users) ──────────────────────────────────────


class TestCaixaAccess(AccessTestBase):
    """Caixa pages accessible to all tenant users (LoginRequired + TenantMixin)."""

    def test_caixa_list_accessible_for_tenant_users(self):
        for user in [self.tenant_admin, self.tenant_user]:
            self.client.force_login(user)
            resp = self.client.get("/caixa/")
            # CaixaListView.dispatch redirects operadores (non-gerentes) to
            # their active register or dashboard, so 302 is valid for them.
            self.assertIn(
                resp.status_code,
                [200, 302],
                f"{user.email} should access /caixa/, got {resp.status_code}",
            )

    def test_caixa_detail_accessible(self):
        self.client.force_login(self.tenant_user)
        resp = self.client.get(f"/caixa/{self.caixa.pk}/")
        self.assertIn(resp.status_code, [200])

    def test_caixa_create_accessible_for_all_tenant(self):
        self.client.force_login(self.tenant_admin)
        resp = self.client.get("/caixa/criar/")
        self.assertIn(resp.status_code, [200])


# ── CLIENTES ──────────────────────────────────────────────────


class TestClientesAccess(AccessTestBase):
    """Clientes accessible to all authenticated tenant users."""

    def test_clientes_list_accessible(self):
        for user in [self.tenant_admin, self.tenant_user]:
            self.client.force_login(user)
            resp = self.client.get("/clientes/")
            self.assertEqual(
                resp.status_code,
                200,
                f"{user.email} should access /clientes/, got {resp.status_code}",
            )

    def test_clientes_create_accessible(self):
        self.client.force_login(self.tenant_admin)
        resp = self.client.get("/clientes/novo/")
        self.assertEqual(resp.status_code, 200)


# ── NFS-e (pode_emitir_nfse) ─────────────────────────────────


class TestNFSeAccess(AccessTestBase):
    """NFS-e pages require pode_emitir_nfse."""

    NFSE_URLS = [
        "/nfse/",
        "/nfse/dashboard/",
    ]

    def test_nfse_accessible_for_tenant_admin(self):
        self.client.force_login(self.tenant_admin)
        for url in self.NFSE_URLS:
            resp = self.client.get(url)
            self.assertIn(
                resp.status_code,
                [200],
                f"Tenant admin should access {url}, got {resp.status_code}",
            )

    def test_nfse_blocked_for_operator_without_permission(self):
        self.client.force_login(self.tenant_user)
        for url in self.NFSE_URLS:
            resp = self.client.get(url)
            self.assertIn(
                resp.status_code,
                [302, 403],
                f"Operator should NOT access {url}, got {resp.status_code}",
            )


# ── FISCAL / CONTABIL ────────────────────────────────────────


class TestFiscalContabilAccess(AccessTestBase):
    """Fiscal and contabil accessible to tenant users (LoginRequired + TenantMixin)."""

    URLS = [
        "/fiscal/livro/",
        "/fiscal/relatorio-iss/",
        "/contabil/plano-contas/",
        "/contabil/lancamentos/",
    ]

    def test_accessible_for_all_tenant_users(self):
        for user in [self.tenant_admin, self.tenant_user]:
            self.client.force_login(user)
            for url in self.URLS:
                resp = self.client.get(url)
                self.assertIn(
                    resp.status_code,
                    [200],
                    f"{user.email} should access {url}, got {resp.status_code}",
                )


# ── AUDITORIA (TenantAdminRequired) ─────────────────────────


class TestAuditoriaAccess(AccessTestBase):
    """Auditoria requires TenantAdminRequiredMixin."""

    def test_auditoria_accessible_for_tenant_admin(self):
        self.client.force_login(self.tenant_admin)
        resp = self.client.get("/auditoria/")
        self.assertIn(resp.status_code, [200])

    def test_auditoria_blocked_for_tenant_user(self):
        self.client.force_login(self.tenant_user)
        resp = self.client.get("/auditoria/")
        self.assertIn(resp.status_code, [302, 403])


# ── RELATÓRIOS (GerenteRequiredMixin) ────────────────────────


class TestRelatoriosAccess(AccessTestBase):
    """Relatórios require GerenteRequiredMixin (pode_aprovar_fechamento)."""

    REPORT_URLS = [
        "/relatorios/",
        "/relatorios/dashboard-analitico/",
        "/relatorios/movimentacoes/",
        "/relatorios/resumo-caixa/",
        "/relatorios/formas-pagamento/",
        "/relatorios/performance-operador/",
        "/relatorios/historico-aberturas/",
        "/relatorios/diferencas-caixa/",
        "/relatorios/log-acoes/",
        "/relatorios/fechamentos-pendentes/",
    ]

    def test_reports_accessible_for_gerente(self):
        self.client.force_login(self.tenant_admin)
        for url in self.REPORT_URLS:
            resp = self.client.get(url)
            self.assertIn(
                resp.status_code,
                [200],
                f"Gerente should access {url}, got {resp.status_code}",
            )

    def test_reports_blocked_for_operator(self):
        self.client.force_login(self.tenant_user)
        for url in self.REPORT_URLS:
            resp = self.client.get(url)
            self.assertIn(
                resp.status_code,
                [302, 403],
                f"Operator should NOT access {url}, got {resp.status_code}",
            )


# ── UNAUTHENTICATED ──────────────────────────────────────────


class TestUnauthenticatedAccess(AccessTestBase):
    """All non-health URLs should redirect to login for unauthenticated users."""

    PROTECTED_URLS = [
        "/",
        "/caixa/",
        "/clientes/",
        "/nfse/",
        "/settings/",
        "/auditoria/",
        "/relatorios/",
        "/platform/",
        "/perfil/",
    ]

    def test_unauthenticated_redirects_to_login(self):
        for url in self.PROTECTED_URLS:
            resp = self.client.get(url)
            self.assertIn(
                resp.status_code,
                [302, 403],
                f"Unauthenticated user should not access {url}, got {resp.status_code}",
            )
            if resp.status_code == 302:
                self.assertIn(
                    "login",
                    resp.url.lower(),
                    f"Should redirect to login, got {resp.url}",
                )


# ── MOVIMENTOS LIST ──────────────────────────────────────────


class TestMovimentosAccess(AccessTestBase):
    """Movimentos list accessible to all authenticated tenant users."""

    def test_movimentos_accessible_for_tenant_users(self):
        for user in [self.tenant_admin, self.tenant_user]:
            self.client.force_login(user)
            resp = self.client.get("/movimentos/")
            self.assertIn(
                resp.status_code,
                [200],
                f"{user.email} should access /movimentos/, got {resp.status_code}",
            )
