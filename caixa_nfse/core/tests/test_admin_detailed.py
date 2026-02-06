import pytest
from django.contrib import admin
from django.test import RequestFactory

from caixa_nfse.core.admin import TenantAdmin, UserAdmin
from caixa_nfse.core.models import Tenant, User
from caixa_nfse.tests.factories import TenantFactory, UserFactory


@pytest.mark.django_db
class TestCoreAdminDetailed:
    def setup_method(self):
        self.tenant = TenantFactory()
        self.superuser = UserFactory(tenant=self.tenant, is_superuser=True, is_staff=True)
        self.factory = RequestFactory()

        # Instantiate Admin classes directly
        self.tenant_admin = TenantAdmin(Tenant, admin.site)
        self.user_admin = UserAdmin(User, admin.site)

    def test_tenant_admin_config(self):
        # Force check list_display logic if dynamic, though mostly static
        assert "razao_social" in self.tenant_admin.list_display
        assert "cnpj" in self.tenant_admin.list_display

    def test_user_admin_permissions(self):
        request = self.factory.get("/")
        request.user = self.superuser

        # Test permission hooks directly
        assert self.user_admin.has_module_permission(request)
        assert self.user_admin.has_add_permission(request)
        assert self.user_admin.has_change_permission(request, self.superuser)
        assert self.user_admin.has_delete_permission(request, self.superuser)

    def test_tenant_admin_fieldsets(self):
        request = self.factory.get("/")
        request.user = self.superuser

        # Access fieldsets to cover configuration logic
        fieldsets = self.tenant_admin.get_fieldsets(request, self.tenant)
        assert fieldsets

    def test_user_admin_custom_actions(self):
        # If there are any custom methods in UserAdmin, invoke them here
        pass
