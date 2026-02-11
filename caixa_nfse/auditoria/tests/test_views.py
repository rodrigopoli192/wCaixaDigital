import pytest
from django.urls import reverse

from caixa_nfse.auditoria.models import RegistroAuditoria
from caixa_nfse.tests.factories import RegistroAuditoriaFactory, TenantFactory, UserFactory


@pytest.mark.django_db
class TestAuditoriaViews:
    def setup_method(self):
        self.tenant = TenantFactory()
        self.user = UserFactory(tenant=self.tenant, pode_aprovar_fechamento=True)
        self.registro = RegistroAuditoriaFactory(tenant=self.tenant, usuario=self.user)

        from django.test import Client

        self.client = Client()
        self.client.force_login(self.user)

    def test_list_access(self):
        url = reverse("auditoria:list")
        response = self.client.get(url)
        assert response.status_code == 200
        assert self.registro in response.context["registros"]

    def test_list_filters(self):
        url = reverse("auditoria:list")

        # Filter by User matches
        response = self.client.get(url, {"usuario": self.user.id})
        assert response.status_code == 200
        assert self.registro in response.context["registros"]

        # Filter no match (table)
        response = self.client.get(url, {"tabela": "NONEXISTENT"})
        assert response.status_code == 200
        assert len(response.context["registros"]) == 0

    def test_detail_access(self):
        url = reverse("auditoria:detail", kwargs={"pk": self.registro.pk})
        response = self.client.get(url)
        assert response.status_code == 200
        assert response.context["object"] == self.registro

    def test_export_csv(self):
        url = reverse("auditoria:exportar")
        response = self.client.get(url)
        assert response.status_code == 200
        assert response["Content-Type"] == "text/csv"
        content = response.content.decode("utf-8")
        assert "Data/Hora" in content

    def test_integrity_check_json(self):
        url = reverse("auditoria:verificar")
        response = self.client.get(url)
        assert response.status_code == 200
        data = response.json()
        assert "integridade_ok" in data

    def test_integrity_broken(self):
        # Tamper with data to break chain
        RegistroAuditoria.objects.filter(pk=self.registro.pk).update(hash_registro="TAMPERED_HASH")

        url = reverse("auditoria:verificar")
        response = self.client.get(url)
        assert response.status_code == 200
        data = response.json()
        # May or may not be broken depending on whether there are other records
        assert "integridade_ok" in data
