import pytest
from django.contrib import admin
from django.test import RequestFactory
from django.urls import reverse

from caixa_nfse.tests.factories import TenantFactory, UserFactory


@pytest.mark.django_db
class TestAdminConfig:
    def setup_method(self):
        self.tenant = TenantFactory()
        self.superuser = UserFactory(tenant=self.tenant, is_superuser=True, is_staff=True)
        self.factory = RequestFactory()
        from django.test import Client

        self.client = Client()
        self.client.force_login(self.superuser)

    def test_all_admin_list_views(self):
        """
        Iterates over all registered admin models and requests their changelist view.
        This provides generic coverage for admin configurations (list_display, list_filter).
        """
        registry = admin.site._registry

        for model, _model_admin in registry.items():
            # Generate URL for the model's change list
            app_label = model._meta.app_label
            model_name = model._meta.model_name
            url_name = f"admin:{app_label}_{model_name}_changelist"

            try:
                url = reverse(url_name)
                response = self.client.get(url)

                # We expect 200 OK for superuser
                assert response.status_code == 200, f"Failed to access admin list for {model_name}"

            except Exception as e:
                pytest.fail(f"Failed attempting to list admin for {model}: {e}")

    def test_admin_index_access(self):
        """Test main admin index page."""
        url = reverse("admin:index")
        response = self.client.get(url)
        assert response.status_code == 200
