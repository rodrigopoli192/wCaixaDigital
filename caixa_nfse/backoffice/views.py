from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView

from caixa_nfse.backoffice.forms import TenantOnboardingForm
from caixa_nfse.core.models import Tenant

User = get_user_model()


class PlatformAdminRequiredMixin(UserPassesTestMixin):
    """Ensure user is a superuser (Platform Admin)."""

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_superuser


class PlatformDashboardView(LoginRequiredMixin, PlatformAdminRequiredMixin, ListView):
    """
    Main dashboard for Platform Admins.
    Lists all Tenants (Companies).
    """

    model = Tenant
    template_name = "backoffice/dashboard.html"
    context_object_name = "tenants"
    ordering = ["-created_at"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["total_tenants"] = Tenant.objects.count()
        context["active_tenants"] = Tenant.objects.filter(ativo=True).count()
        context["total_users"] = User.objects.count()
        return context


class TenantOnboardingView(LoginRequiredMixin, PlatformAdminRequiredMixin, CreateView):
    """
    Unified form to create a Tenant + Admin User.
    """

    form_class = TenantOnboardingForm
    template_name = "backoffice/tenant_form.html"
    success_url = reverse_lazy("backoffice:dashboard")

    def form_valid(self, form):
        # The form save method handles the atomic creation of Tenant + User
        form.save()
        return redirect(self.success_url)
