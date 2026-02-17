"""
Tests for NFS-e report views: CSV export, Dashboard, API Log.
Covers lines missing from nfse/reports.py.
"""

import pytest
from django.test import Client
from django.urls import reverse

from caixa_nfse.nfse.models import StatusNFSe
from caixa_nfse.tests.factories import TenantFactory, UserFactory


@pytest.fixture
def nfse_user(db):
    tenant = TenantFactory()
    user = UserFactory(
        tenant=tenant,
        pode_emitir_nfse=True,
        pode_aprovar_fechamento=True,
    )
    return user, tenant


@pytest.mark.django_db
class TestNFSeExportCSV:
    def test_csv_export_empty(self, nfse_user):
        user, tenant = nfse_user
        client = Client()
        client.force_login(user)

        response = client.get(reverse("nfse:export_csv"))
        assert response.status_code == 200
        assert response["Content-Type"] == "text/csv; charset=utf-8"

    def test_csv_export_with_status_filter(self, nfse_user):
        user, tenant = nfse_user
        client = Client()
        client.force_login(user)

        response = client.get(reverse("nfse:export_csv"), {"status": StatusNFSe.AUTORIZADA})
        assert response.status_code == 200

    def test_csv_export_with_date_filters(self, nfse_user):
        user, tenant = nfse_user
        client = Client()
        client.force_login(user)

        response = client.get(
            reverse("nfse:export_csv"),
            {"data_inicio": "2026-01-01", "data_fim": "2026-12-31"},
        )
        assert response.status_code == 200

    def test_csv_export_with_cliente_filter(self, nfse_user):
        user, tenant = nfse_user
        client = Client()
        client.force_login(user)

        response = client.get(reverse("nfse:export_csv"), {"cliente": "Teste"})
        assert response.status_code == 200

    def test_csv_export_requires_permission(self, db):
        tenant = TenantFactory()
        user = UserFactory(tenant=tenant, pode_emitir_nfse=False)
        client = Client()
        client.force_login(user)

        response = client.get(reverse("nfse:export_csv"))
        assert response.status_code == 403


@pytest.mark.django_db
class TestNFSeDashboard:
    def test_dashboard_renders(self, nfse_user):
        user, tenant = nfse_user
        client = Client()
        client.force_login(user)

        response = client.get(reverse("nfse:dashboard"))
        assert response.status_code == 200
        assert "kpis" in response.context
        assert "monthly_data" in response.context
        assert "top_clients" in response.context
        assert "status_breakdown" in response.context

    def test_dashboard_custom_meses(self, nfse_user):
        user, tenant = nfse_user
        client = Client()
        client.force_login(user)

        response = client.get(reverse("nfse:dashboard"), {"meses": "6"})
        assert response.status_code == 200
        assert response.context["meses"] == 6


@pytest.mark.django_db
class TestNFSeApiLogList:
    def test_api_log_list_renders(self, nfse_user):
        user, tenant = nfse_user
        client = Client()
        client.force_login(user)

        response = client.get(reverse("nfse:api_log"))
        assert response.status_code == 200

    def test_api_log_requires_manager(self, db):
        tenant = TenantFactory()
        user = UserFactory(tenant=tenant, pode_aprovar_fechamento=False)
        client = Client()
        client.force_login(user)

        response = client.get(reverse("nfse:api_log"))
        assert response.status_code == 403
