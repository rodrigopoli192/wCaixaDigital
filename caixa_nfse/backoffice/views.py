from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

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

    def get_queryset(self):
        from django.db.models import Count

        return super().get_queryset().annotate(user_count=Count("usuarios"))

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


class TenantUpdateView(LoginRequiredMixin, PlatformAdminRequiredMixin, UpdateView):
    """
    Edit Tenant details.
    """

    model = Tenant
    form_class = TenantOnboardingForm  # Can reuse or use specific update form
    template_name = "backoffice/tenant_update.html"
    success_url = reverse_lazy("backoffice:dashboard")
    context_object_name = "tenant"

    def get_form_class(self):
        # Import dynamically to avoid circular imports or use the one defined in forms.py
        from caixa_nfse.backoffice.forms import TenantUpdateForm

        return TenantUpdateForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["usuarios"] = self.object.usuarios.all()
        return context


class TenantDeleteView(LoginRequiredMixin, PlatformAdminRequiredMixin, DeleteView):
    """
    Delete (or deactivate) a Tenant.
    """

    model = Tenant
    template_name = "backoffice/tenant_confirm_delete.html"
    success_url = reverse_lazy("backoffice:dashboard")
    context_object_name = "tenant"
