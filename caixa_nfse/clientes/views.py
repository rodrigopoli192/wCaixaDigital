"""
Clientes views.
"""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, UpdateView
from django_filters.views import FilterView
from django_tables2 import SingleTableMixin

from .filters import ClienteFilter
from .forms import ClienteForm
from .models import Cliente
from .tables import ClienteTable


class TenantMixin:
    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.tenant:
            return qs.filter(tenant=self.request.user.tenant)
        return qs.none()


class ClienteListView(LoginRequiredMixin, TenantMixin, SingleTableMixin, FilterView):
    model = Cliente
    table_class = ClienteTable
    filterset_class = ClienteFilter
    template_name = "clientes/cliente_list.html"
    paginate_by = 25


class ClienteDetailView(LoginRequiredMixin, TenantMixin, DetailView):
    model = Cliente
    template_name = "clientes/cliente_detail.html"


class ClienteCreateView(LoginRequiredMixin, CreateView):
    model = Cliente
    form_class = ClienteForm
    template_name = "clientes/cliente_form.html"
    success_url = reverse_lazy("clientes:list")

    def form_valid(self, form):
        form.instance.tenant = self.request.user.tenant
        form.instance.created_by = self.request.user
        messages.success(self.request, "Cliente cadastrado com sucesso!")
        return super().form_valid(form)


class ClienteUpdateView(LoginRequiredMixin, TenantMixin, UpdateView):
    model = Cliente
    form_class = ClienteForm
    template_name = "clientes/cliente_form.html"
    success_url = reverse_lazy("clientes:list")

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(self.request, "Cliente atualizado com sucesso!")
        return super().form_valid(form)
