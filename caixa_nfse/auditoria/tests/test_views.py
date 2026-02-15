from datetime import date

import pytest
from django.test import Client
from django.urls import reverse

from caixa_nfse.auditoria.models import RegistroAuditoria
from caixa_nfse.tests.factories import RegistroAuditoriaFactory, TenantFactory, UserFactory


@pytest.mark.django_db
class TestAuditoriaViews:
    def setup_method(self):
        self.tenant = TenantFactory()
        self.user = UserFactory(tenant=self.tenant, pode_aprovar_fechamento=True)
        self.registro = RegistroAuditoriaFactory(tenant=self.tenant, usuario=self.user)

        self.client = Client()
        self.client.force_login(self.user)

    # ------------------------------------------------------------------
    # List View — basic access
    # ------------------------------------------------------------------

    def test_list_access(self):
        url = reverse("auditoria:list")
        response = self.client.get(url)
        assert response.status_code == 200
        assert self.registro in response.context["registros"]

    # ------------------------------------------------------------------
    # List View — filters (cover all branches)
    # ------------------------------------------------------------------

    def test_list_filter_usuario(self):
        url = reverse("auditoria:list")
        response = self.client.get(url, {"usuario": self.user.id})
        assert response.status_code == 200
        assert self.registro in response.context["registros"]

    def test_list_filter_tabela_no_match(self):
        url = reverse("auditoria:list")
        response = self.client.get(url, {"tabela": "NONEXISTENT"})
        assert response.status_code == 200
        assert len(response.context["registros"]) == 0

    def test_list_filter_tabela_match(self):
        url = reverse("auditoria:list")
        response = self.client.get(url, {"tabela": self.registro.tabela})
        assert response.status_code == 200
        assert self.registro in response.context["registros"]

    def test_list_filter_acao(self):
        url = reverse("auditoria:list")
        response = self.client.get(url, {"acao": self.registro.acao})
        assert response.status_code == 200
        assert self.registro in response.context["registros"]

    def test_list_filter_data_inicio(self):
        url = reverse("auditoria:list")
        today = date.today().isoformat()
        response = self.client.get(url, {"data_inicio": today})
        assert response.status_code == 200

    def test_list_filter_data_fim(self):
        url = reverse("auditoria:list")
        today = date.today().isoformat()
        response = self.client.get(url, {"data_fim": today})
        assert response.status_code == 200

    def test_list_filter_date_range(self):
        url = reverse("auditoria:list")
        today = date.today().isoformat()
        response = self.client.get(url, {"data_inicio": today, "data_fim": today})
        assert response.status_code == 200
        assert self.registro in response.context["registros"]

    def test_list_filter_all_combined(self):
        url = reverse("auditoria:list")
        today = date.today().isoformat()
        response = self.client.get(
            url,
            {
                "tabela": self.registro.tabela,
                "acao": self.registro.acao,
                "usuario": self.user.id,
                "data_inicio": today,
                "data_fim": today,
            },
        )
        assert response.status_code == 200
        assert self.registro in response.context["registros"]

    # ------------------------------------------------------------------
    # Detail View
    # ------------------------------------------------------------------

    def test_detail_access(self):
        url = reverse("auditoria:detail", kwargs={"pk": self.registro.pk})
        response = self.client.get(url)
        assert response.status_code == 200
        assert response.context["registro"] == self.registro

    def test_detail_tenant_isolation(self):
        """Registro de outro tenant não deve ser acessível."""
        other_tenant = TenantFactory()
        other_registro = RegistroAuditoriaFactory(tenant=other_tenant)
        url = reverse("auditoria:detail", kwargs={"pk": other_registro.pk})
        response = self.client.get(url)
        assert response.status_code == 404

    # ------------------------------------------------------------------
    # Export View
    # ------------------------------------------------------------------

    def test_export_csv(self):
        url = reverse("auditoria:exportar")
        response = self.client.get(url)
        assert response.status_code == 200
        assert response["Content-Type"] == "text/csv"
        content = response.content.decode("utf-8")
        assert "Data/Hora" in content
        assert self.registro.tabela in content

    def test_export_csv_with_date_filters(self):
        url = reverse("auditoria:exportar")
        today = date.today().isoformat()
        response = self.client.get(url, {"data_inicio": today, "data_fim": today})
        assert response.status_code == 200
        assert response["Content-Type"] == "text/csv"

    def test_export_csv_no_usuario(self):
        """Registro sem usuario deve exportar string vazia no campo."""
        RegistroAuditoriaFactory(tenant=self.tenant, usuario=None)
        url = reverse("auditoria:exportar")
        response = self.client.get(url)
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert "Data/Hora" in content

    # ------------------------------------------------------------------
    # Integrity Check
    # ------------------------------------------------------------------

    def test_integrity_check_json(self):
        url = reverse("auditoria:verificar")
        response = self.client.get(url)
        assert response.status_code == 200
        data = response.json()
        assert "integridade_ok" in data
        assert "total_corrompidos" in data

    def test_integrity_broken(self):
        RegistroAuditoria.objects.filter(pk=self.registro.pk).update(hash_registro="TAMPERED_HASH")
        url = reverse("auditoria:verificar")
        response = self.client.get(url)
        assert response.status_code == 200
        data = response.json()
        assert "integridade_ok" in data

    # ------------------------------------------------------------------
    # Authorization — 403 for non-admin
    # ------------------------------------------------------------------

    def test_list_forbidden_for_operador(self):
        operador = UserFactory(tenant=self.tenant, pode_aprovar_fechamento=False)
        client = Client()
        client.force_login(operador)
        response = client.get(reverse("auditoria:list"))
        assert response.status_code == 403

    def test_detail_forbidden_for_operador(self):
        operador = UserFactory(tenant=self.tenant, pode_aprovar_fechamento=False)
        client = Client()
        client.force_login(operador)
        url = reverse("auditoria:detail", kwargs={"pk": self.registro.pk})
        response = client.get(url)
        assert response.status_code == 403

    def test_export_forbidden_for_operador(self):
        operador = UserFactory(tenant=self.tenant, pode_aprovar_fechamento=False)
        client = Client()
        client.force_login(operador)
        response = client.get(reverse("auditoria:exportar"))
        assert response.status_code == 403

    def test_verificar_forbidden_for_operador(self):
        operador = UserFactory(tenant=self.tenant, pode_aprovar_fechamento=False)
        client = Client()
        client.force_login(operador)
        response = client.get(reverse("auditoria:verificar"))
        assert response.status_code == 403
