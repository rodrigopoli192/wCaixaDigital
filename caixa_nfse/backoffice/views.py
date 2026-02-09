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


class TenantUserCreateView(LoginRequiredMixin, PlatformAdminRequiredMixin, CreateView):
    """
    Create a new user for a specific Tenant (modal form).
    """

    model = User
    template_name = "backoffice/partials/tenant_user_form.html"

    def get_form_class(self):
        from caixa_nfse.backoffice.forms import TenantUserForm

        return TenantUserForm

    def get_tenant(self):
        return Tenant.objects.get(pk=self.kwargs["tenant_pk"])

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["tenant"] = self.get_tenant()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["tenant"] = self.get_tenant()
        context["is_new"] = True
        return context

    def form_valid(self, form):
        form.save()
        # Return success partial that triggers HTMX refresh
        from django.http import HttpResponse

        return HttpResponse(
            '<div hx-trigger="load" hx-get="'
            + str(reverse_lazy("backoffice:tenant_edit", kwargs={"pk": self.kwargs["tenant_pk"]}))
            + '" hx-target="body" hx-swap="outerHTML"></div>'
        )


class TenantUserUpdateView(LoginRequiredMixin, PlatformAdminRequiredMixin, UpdateView):
    """
    Edit an existing user within a Tenant (modal form).
    """

    model = User
    template_name = "backoffice/partials/tenant_user_form.html"

    def get_form_class(self):
        from caixa_nfse.backoffice.forms import TenantUserForm

        return TenantUserForm

    def get_tenant(self):
        return Tenant.objects.get(pk=self.kwargs["tenant_pk"])

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["tenant"] = self.get_tenant()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["tenant"] = self.get_tenant()
        context["is_new"] = False
        return context

    def form_valid(self, form):
        form.save()
        from django.http import HttpResponse

        return HttpResponse(
            '<div hx-trigger="load" hx-get="'
            + str(reverse_lazy("backoffice:tenant_edit", kwargs={"pk": self.kwargs["tenant_pk"]}))
            + '" hx-target="body" hx-swap="outerHTML"></div>'
        )


class SistemaListView(LoginRequiredMixin, PlatformAdminRequiredMixin, ListView):
    """
    List all registered external Systems.
    """

    model = None  # Loaded dynamically to avoid circular import quirks
    template_name = "backoffice/sistema_list.html"
    context_object_name = "sistemas"
    ordering = ["nome"]

    def get_queryset(self):
        from caixa_nfse.backoffice.models import Sistema

        return Sistema.objects.all()


class SistemaCreateView(LoginRequiredMixin, PlatformAdminRequiredMixin, CreateView):
    template_name = "backoffice/partials/sistema_form.html"
    success_url = reverse_lazy("backoffice:sistema_list")

    def get_form_class(self):
        from caixa_nfse.backoffice.forms import SistemaForm

        return SistemaForm

    def form_valid(self, form):
        form.save()
        from django.http import HttpResponse

        # HTMX Refresh of the list
        return HttpResponse(
            '<script>window.location.href = "' + str(self.success_url) + '"</script>'
        )


class SistemaUpdateView(LoginRequiredMixin, PlatformAdminRequiredMixin, UpdateView):
    """
    Update Sistema and List its Routines.
    """

    model = None
    template_name = "backoffice/sistema_update.html"
    context_object_name = "sistema"
    success_url = reverse_lazy("backoffice:sistema_list")

    def get_queryset(self):
        from caixa_nfse.backoffice.models import Sistema

        return Sistema.objects.all()

    def get_form_class(self):
        from caixa_nfse.backoffice.forms import SistemaForm

        return SistemaForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["rotinas"] = self.object.rotinas.all()
        return context


class SistemaDeleteView(LoginRequiredMixin, PlatformAdminRequiredMixin, DeleteView):
    model = None
    template_name = "backoffice/partials/sistema_confirm_delete.html"
    success_url = reverse_lazy("backoffice:sistema_list")

    def get_queryset(self):
        from caixa_nfse.backoffice.models import Sistema

        return Sistema.objects.all()


class RotinaCreateView(LoginRequiredMixin, PlatformAdminRequiredMixin, CreateView):
    template_name = "backoffice/partials/rotina_form.html"

    def get_form_class(self):
        from caixa_nfse.backoffice.forms import RotinaForm

        return RotinaForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from caixa_nfse.backoffice.forms import MapeamentoInlineFormSet
        from caixa_nfse.backoffice.models import Sistema

        context["sistema"] = Sistema.objects.get(pk=self.kwargs["sistema_pk"])
        if self.request.POST:
            context["mapeamento_formset"] = MapeamentoInlineFormSet(self.request.POST)
        else:
            context["mapeamento_formset"] = MapeamentoInlineFormSet()
        return context

    def form_valid(self, form):
        from django.http import HttpResponse

        context = self.get_context_data()
        formset = context["mapeamento_formset"]

        form.instance.sistema_id = self.kwargs["sistema_pk"]
        rotina = form.save()

        if formset.is_valid():
            formset.instance = rotina
            formset.save()

        return HttpResponse("<script>window.location.reload()</script>")


class RotinaUpdateView(LoginRequiredMixin, PlatformAdminRequiredMixin, UpdateView):
    template_name = "backoffice/partials/rotina_form.html"

    def get_queryset(self):
        from caixa_nfse.backoffice.models import Rotina

        return Rotina.objects.all()

    def get_form_class(self):
        from caixa_nfse.backoffice.forms import RotinaForm

        return RotinaForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from caixa_nfse.backoffice.forms import MapeamentoInlineFormSet

        if self.request.POST:
            context["mapeamento_formset"] = MapeamentoInlineFormSet(
                self.request.POST, instance=self.object
            )
        else:
            context["mapeamento_formset"] = MapeamentoInlineFormSet(instance=self.object)
        return context

    def form_valid(self, form):
        from django.http import HttpResponse

        context = self.get_context_data()
        formset = context["mapeamento_formset"]

        rotina = form.save()

        if formset.is_valid():
            formset.instance = rotina
            formset.save()

        return HttpResponse("<script>window.location.reload()</script>")


class RotinaDeleteView(LoginRequiredMixin, PlatformAdminRequiredMixin, DeleteView):
    template_name = "backoffice/partials/rotina_confirm_delete.html"

    def get_queryset(self):
        from caixa_nfse.backoffice.models import Rotina

        return Rotina.objects.all()

    def get_success_url(self):
        return reverse_lazy("backoffice:sistema_edit", kwargs={"pk": self.object.sistema.pk})
