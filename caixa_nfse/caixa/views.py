"""
Caixa views.
"""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, UpdateView
from django_filters.views import FilterView
from django_tables2 import SingleTableMixin

from .filters import CaixaFilter, MovimentoFilter
from .forms import AbrirCaixaForm, FechamentoCaixaForm, MovimentoCaixaForm
from .models import (
    AberturaCaixa,
    Caixa,
    FechamentoCaixa,
    MovimentoCaixa,
    StatusCaixa,
    StatusFechamento,
)
from .tables import CaixaTable, MovimentoTable


class TenantMixin:
    """Mixin to filter queryset by user's tenant."""

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.tenant:
            return qs.filter(tenant=self.request.user.tenant)
        return qs.none()


class CaixaListView(LoginRequiredMixin, TenantMixin, SingleTableMixin, FilterView):
    """Lista de caixas."""

    model = Caixa
    table_class = CaixaTable
    filterset_class = CaixaFilter
    template_name = "caixa/caixa_list.html"
    paginate_by = 20

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Caixas"
        return context


class CaixaDetailView(LoginRequiredMixin, TenantMixin, DetailView):
    """Detalhes do caixa."""

    model = Caixa
    template_name = "caixa/caixa_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Caixa {self.object.identificador}"
        context["abertura_atual"] = self.object.aberturas.filter(fechado=False).first()
        context["ultimas_aberturas"] = self.object.aberturas.all()[:10]
        return context


class AbrirCaixaView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Abertura de caixa."""

    model = AberturaCaixa
    form_class = AbrirCaixaForm
    template_name = "caixa/abrir_caixa.html"

    def test_func(self):
        return self.request.user.pode_operar_caixa

    def get_caixa(self):
        return get_object_or_404(
            Caixa,
            pk=self.kwargs["pk"],
            tenant=self.request.user.tenant,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["caixa"] = self.get_caixa()
        context["page_title"] = f"Abrir {context['caixa'].identificador}"
        return context

    def form_valid(self, form):
        caixa = self.get_caixa()

        if caixa.status != StatusCaixa.FECHADO:
            messages.error(self.request, "Este caixa já está aberto ou bloqueado.")
            return redirect("caixa:detail", pk=caixa.pk)

        with transaction.atomic():
            abertura = form.save(commit=False)
            abertura.tenant = self.request.user.tenant
            abertura.caixa = caixa
            abertura.operador = self.request.user
            abertura.created_by = self.request.user
            abertura.save()

            # Atualiza status do caixa
            caixa.status = StatusCaixa.ABERTO
            caixa.operador_atual = self.request.user
            caixa.saldo_atual = abertura.saldo_abertura
            caixa.save()

        messages.success(self.request, f"Caixa {caixa.identificador} aberto com sucesso!")
        return redirect("caixa:detail", pk=caixa.pk)


class FecharCaixaView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Fechamento de caixa."""

    model = FechamentoCaixa
    form_class = FechamentoCaixaForm
    template_name = "caixa/fechar_caixa.html"

    def test_func(self):
        return self.request.user.pode_operar_caixa

    def get_caixa(self):
        return get_object_or_404(
            Caixa,
            pk=self.kwargs["pk"],
            tenant=self.request.user.tenant,
        )

    def get_abertura(self):
        caixa = self.get_caixa()
        return caixa.aberturas.filter(fechado=False).first()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        caixa = self.get_caixa()
        abertura = self.get_abertura()

        context["caixa"] = caixa
        context["abertura"] = abertura
        context["page_title"] = f"Fechar {caixa.identificador}"

        if abertura:
            # Calcula totais por forma de pagamento
            context["saldo_sistema"] = abertura.saldo_movimentos
            context["totais_forma_pagamento"] = abertura.movimentos.values(
                "forma_pagamento__nome", "tipo"
            ).annotate(total=Sum("valor"))

        return context

    def get_template_names(self):
        if self.request.headers.get("HX-Request"):
            return ["caixa/partials/fechar_caixa_form.html"]
        return [self.template_name]

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        abertura = self.get_abertura()
        if abertura:
            kwargs["saldo_sistema"] = abertura.saldo_movimentos
        return kwargs

    def form_valid(self, form):
        caixa = self.get_caixa()
        abertura = self.get_abertura()

        if not abertura:
            messages.error(self.request, "Não há abertura de caixa para fechar.")
            return redirect("caixa:detail", pk=caixa.pk)

        with transaction.atomic():
            fechamento = form.save(commit=False)
            fechamento.tenant = self.request.user.tenant
            fechamento.abertura = abertura
            fechamento.operador = self.request.user
            fechamento.saldo_sistema = abertura.saldo_movimentos
            fechamento.created_by = self.request.user
            fechamento.observacao = form.cleaned_data.get("observacoes", "")

            # Monta detalhamento
            fechamento.detalhamento = self._calcular_detalhamento(abertura)

            fechamento.save()

            # Se não requer aprovação, aprova automaticamente
            if not fechamento.requer_aprovacao:
                fechamento.aprovar(self.request.user)
                messages.success(self.request, "Caixa fechado e aprovado automaticamente!")
            else:
                messages.warning(
                    self.request,
                    f"Caixa fechado com diferença de R$ {fechamento.diferenca}. "
                    "Aguardando aprovação.",
                )

        if self.request.headers.get("HX-Request"):
            from django.http import HttpResponse

            response = HttpResponse()
            response["HX-Refresh"] = "true"
            return response

        return redirect("caixa:detail", pk=caixa.pk)

    def _calcular_detalhamento(self, abertura):
        """Calcula totais por forma de pagamento."""
        from collections import defaultdict

        detalhamento = defaultdict(lambda: {"entradas": 0, "saidas": 0})

        for mov in abertura.movimentos.select_related("forma_pagamento"):
            fp = mov.forma_pagamento.nome
            if mov.is_entrada:
                detalhamento[fp]["entradas"] += float(mov.valor)
            else:
                detalhamento[fp]["saidas"] += float(mov.valor)

        return dict(detalhamento)


class NovoMovimentoView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Novo movimento de caixa."""

    model = MovimentoCaixa
    form_class = MovimentoCaixaForm
    template_name = "caixa/movimento_form.html"

    def test_func(self):
        return self.request.user.pode_operar_caixa

    def get_abertura(self):
        return get_object_or_404(
            AberturaCaixa,
            pk=self.kwargs["pk"],
            tenant=self.request.user.tenant,
            fechado=False,
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["tenant"] = self.request.user.tenant
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        abertura = self.get_abertura()
        context["abertura"] = abertura
        context["caixa"] = abertura.caixa
        context["page_title"] = "Novo Movimento"
        context["saldo_atual"] = abertura.saldo_movimentos
        return context

    def get_template_names(self):
        if self.request.headers.get("HX-Request"):
            return ["caixa/partials/movimento_form.html"]
        return [self.template_name]

    def form_valid(self, form):
        abertura = self.get_abertura()

        with transaction.atomic():
            movimento = form.save(commit=False)
            movimento.tenant = self.request.user.tenant
            movimento.abertura = abertura
            movimento.created_by = self.request.user
            movimento.save()

            # Atualiza saldo do caixa
            caixa = abertura.caixa
            if movimento.is_entrada:
                caixa.saldo_atual += movimento.valor
            else:
                caixa.saldo_atual -= movimento.valor
            caixa.save(update_fields=["saldo_atual"])

        messages.success(self.request, "Movimento registrado com sucesso!")

        # Se for HTMX, recarrega a página para atualizar cards/tabelas
        if self.request.headers.get("HX-Request"):
            from django.http import HttpResponse

            response = HttpResponse()
            response["HX-Refresh"] = "true"
            return response

        return redirect("caixa:detail", pk=abertura.caixa.pk)


class ListaMovimentosView(LoginRequiredMixin, TenantMixin, SingleTableMixin, FilterView):
    """Lista de movimentos de uma abertura."""

    model = MovimentoCaixa
    table_class = MovimentoTable
    filterset_class = MovimentoFilter
    template_name = "caixa/movimento_list.html"
    paginate_by = 50

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(abertura_id=self.kwargs["pk"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["abertura"] = get_object_or_404(
            AberturaCaixa,
            pk=self.kwargs["pk"],
            tenant=self.request.user.tenant,
        )
        context["page_title"] = "Movimentos"
        return context


class FechamentosPendentesView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """Lista de fechamentos pendentes de aprovação."""

    model = FechamentoCaixa
    template_name = "caixa/fechamentos_pendentes.html"
    context_object_name = "fechamentos"

    def test_func(self):
        return self.request.user.pode_aprovar_fechamento

    def get_queryset(self):
        return FechamentoCaixa.objects.filter(
            tenant=self.request.user.tenant,
            status=StatusFechamento.PENDENTE,
        ).select_related("abertura__caixa", "operador")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Fechamentos Pendentes"
        return context


class AprovarFechamentoView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Aprovar ou rejeitar fechamento."""

    model = FechamentoCaixa
    fields = ["observacao_aprovador"]
    template_name = "caixa/aprovar_fechamento.html"
    success_url = reverse_lazy("caixa:fechamentos_pendentes")

    def test_func(self):
        return self.request.user.pode_aprovar_fechamento

    def get_queryset(self):
        return FechamentoCaixa.objects.filter(
            tenant=self.request.user.tenant,
            status=StatusFechamento.PENDENTE,
        )

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        action = request.POST.get("action")
        observacao = request.POST.get("observacao_aprovador", "")

        if action == "aprovar":
            self.object.aprovar(request.user, observacao)
            messages.success(request, "Fechamento aprovado com sucesso!")
        elif action == "rejeitar":
            if not observacao:
                messages.error(request, "Justificativa obrigatória para rejeição.")
                return self.get(request, *args, **kwargs)
            self.object.rejeitar(request.user, observacao)
            messages.warning(request, "Fechamento rejeitado.")

        return redirect(self.success_url)
