import pytest
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from caixa_nfse.auditoria.models import RegistroAuditoria
from caixa_nfse.tests.factories import RegistroAuditoriaFactory, TenantFactory, UserFactory


@pytest.mark.django_db
class TestAuditoriaViews:
    def setup_method(self):
        self.tenant = TenantFactory()
        self.user = UserFactory(tenant=self.tenant)
        self.registro = RegistroAuditoriaFactory(tenant=self.tenant, usuario=self.user)

        from django.test import Client

        self.client = Client()
        self.client.force_login(self.user)

        # Assign permissions
        content_type = ContentType.objects.get_for_model(RegistroAuditoria)
        p1 = Permission.objects.get(codename="view_registroauditoria", content_type=content_type)
        # Assuming permissions exist, if not create them
        # Note: 'view_audit_report' and 'export_audit_log' might be custom permissions
        # If they are not in permissions table, we might skip or fail.
        # Let's verify standard permissions first.
        self.user.user_permissions.add(p1)

        # Handle custom permissions potentially missing in test DB setup if migration is handled differently
        # For now, let's try to fetch or create
        try:
            p2, _ = Permission.objects.get_or_create(
                codename="view_audit_report", content_type=content_type, name="View Report"
            )
            self.user.user_permissions.add(p2)
            p3, _ = Permission.objects.get_or_create(
                codename="export_audit_log", content_type=content_type, name="Export Log"
            )
            self.user.user_permissions.add(p3)
        except Exception:
            pass
        self.user.save()

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

        # Filter by Action match
        self.registro.acao = "LOGIN"
        self.registro.save()
        response = self.client.get(url, {"acao": "LOGIN"})
        assert response.status_code == 200
        assert self.registro in response.context["registros"]

        # Filter by Date Range match
        data_hj = self.registro.data_hora.date().isoformat()
        response = self.client.get(url, {"data_inicio": data_hj, "data_fim": data_hj})
        assert response.status_code == 200
        assert self.registro in response.context["registros"]

        # Filter by Date Range NO match
        response = self.client.get(url, {"data_inicio": "2000-01-01", "data_fim": "2000-01-01"})
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
        assert str(self.registro.registro_id) in content
        assert "EXPORT" in content  # The last exported log

    def test_integrity_check_json(self):
        url = reverse("auditoria:integrity")
        response = self.client.get(url)
        assert response.status_code == 200
        data = response.json()
        assert "integridade_ok" in data
        assert (
            data["integridade_ok"] is True
        )  # Factory data should be consistent by default if factory handles hash

    def test_integrity_report_fail(self):
        # corrupt data
        self.registro.hash_registro = "invalid"
        self.registro.save()

        url = reverse("auditoria:integrity")
        response = self.client.get(url)
        assert response.status_code == 200
        data = response.json()
        assert data["integridade_ok"] is False
