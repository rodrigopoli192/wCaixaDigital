"""
Caixa views.
"""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
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
        context["hoje"] = timezone.now().date()
        return context


class CaixaCreateView(LoginRequiredMixin, TenantMixin, CreateView):
    """Criar novo caixa."""

    model = Caixa
    fields = ["identificador", "tipo"]
    template_name = "caixa/caixa_form.html"
    success_url = reverse_lazy("caixa:list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Novo Caixa"
        return context

    def form_valid(self, form):
        form.instance.tenant = self.request.user.tenant
        messages.success(self.request, f"Caixa {form.instance.identificador} criado com sucesso!")
        return super().form_valid(form)


class CaixaUpdateView(LoginRequiredMixin, TenantMixin, UpdateView):
    """Editar caixa existente."""

    model = Caixa
    fields = ["identificador", "tipo", "ativo"]
    template_name = "caixa/caixa_form.html"
    success_url = reverse_lazy("caixa:list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Editar {self.object.identificador}"
        context["is_edit"] = True
        return context

    def form_valid(self, form):
        messages.success(self.request, f"Caixa {form.instance.identificador} atualizado!")
        return super().form_valid(form)


class CaixaDetailView(LoginRequiredMixin, TenantMixin, DetailView):
    """Detalhes do caixa."""

    model = Caixa
    template_name = "caixa/caixa_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Caixa {self.object.identificador}"
        context["abertura_atual"] = self.object.aberturas.filter(fechado=False).first()
        context["ultimas_aberturas"] = self.object.aberturas.all()[:10]
        context["hoje"] = timezone.now().date()
        return context


class AbrirCaixaView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Abertura de caixa."""

    model = AberturaCaixa
    form_class = AbrirCaixaForm
    template_name = "caixa/abrir_caixa.html"

    def test_func(self):
        return self.request.user.pode_operar_caixa

    def dispatch(self, request, *args, **kwargs):
        caixa = self.get_caixa()
        if caixa.status != StatusCaixa.FECHADO:
            messages.error(request, "Este caixa já está aberto ou bloqueado.")
            return redirect("caixa:detail", pk=caixa.pk)
        return super().dispatch(request, *args, **kwargs)

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

    def get_template_names(self):
        if self.request.headers.get("HX-Request"):
            return ["caixa/partials/abrir_caixa_form.html"]
        return [self.template_name]

    def form_valid(self, form):
        caixa = self.get_caixa()

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

        if self.request.headers.get("HX-Request"):
            from django.http import HttpResponse

            response = HttpResponse()
            response["HX-Refresh"] = "true"
            return response

        return redirect("caixa:detail", pk=caixa.pk)


class FecharCaixaView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Fechamento de caixa."""

    model = FechamentoCaixa
    form_class = FechamentoCaixaForm
    template_name = "caixa/fechar_caixa.html"

    def test_func(self):
        """
        Allow closing if:
        1. User has 'pode_operar_caixa' AND
        2. User is the one who opened the register OR has 'pode_aprovar_fechamento' (manager)
        """
        if not self.request.user.pode_operar_caixa:
            return False

        abertura = self.get_abertura()
        if not abertura:
            return False

        # User who opened can close their own register
        if abertura.operador == self.request.user:
            return True

        # Managers can close any register
        if self.request.user.pode_aprovar_fechamento:
            return True

        return False

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

        # Check if closing another user's register
        if abertura and abertura.operador != self.request.user:
            context["fechando_outro_operador"] = True
            context["operador_original"] = abertura.operador

        if abertura:
            # Calcula totais por forma de pagamento
            context["saldo_sistema"] = abertura.saldo_movimentos
            # Agrupa totais APENAS por forma de pagamento (não por tipo)
            context["totais_forma_pagamento"] = (
                abertura.movimentos.values("forma_pagamento__nome")
                .annotate(total=Sum("valor"))
                .order_by("-total")
            )

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

    def dispatch(self, request, *args, **kwargs):
        """Valida se a abertura é do dia atual."""
        abertura = self.get_abertura()
        if not abertura.is_operacional_hoje:
            messages.error(
                request, "Não é permitido lançar movimentos em datas diferentes da abertura."
            )
            # Se for HTMX, retorna erro 403 para não renderizar form
            if request.headers.get("HX-Request"):
                from django.http import HttpResponseForbidden

                return HttpResponseForbidden("Operação não permitida em datas retroativas.")

            return redirect("caixa:lista_movimentos", pk=abertura.pk)

        return super().dispatch(request, *args, **kwargs)

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
        return qs.filter(abertura_id=self.kwargs["pk"]).select_related("cliente", "forma_pagamento")

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
            return redirect(self.success_url)

        if action == "rejeitar":
            if not observacao:
                messages.error(request, "Justificativa obrigatória para rejeição.")
                return super().get(request, *args, **kwargs)

            self.object.rejeitar(request.user, observacao)
            messages.warning(request, "Fechamento rejeitado.")
            return redirect(self.success_url)

        return redirect(self.success_url)


class ImportarMovimentosView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """Modal for importing movements from external databases."""

    model = AberturaCaixa
    template_name = "caixa/partials/importar_form.html"

    def test_func(self):
        return self.request.user.pode_operar_caixa

    def get_queryset(self):
        return AberturaCaixa.objects.filter(tenant=self.request.user.tenant, fechado=False)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from caixa_nfse.backoffice.models import Rotina
        from caixa_nfse.core.models import ConexaoExterna

        context["abertura"] = self.object
        conexoes = ConexaoExterna.objects.filter(
            tenant=self.request.user.tenant, ativo=True
        ).select_related("sistema")

        conexoes_tree = []
        for con in conexoes:
            rotinas = list(
                Rotina.objects.filter(sistema=con.sistema, ativo=True).values(
                    "pk", "nome", "descricao"
                )
            )
            if rotinas:
                conexoes_tree.append({"conexao": con, "rotinas": rotinas})
        context["conexoes_tree"] = conexoes_tree
        return context

    def post(self, request, *args, **kwargs):
        """Two-step import: buscar (preview) then importar (save selected)."""
        import json
        import logging

        from django.http import HttpResponse
        from django.template.loader import render_to_string

        from caixa_nfse.backoffice.models import Rotina
        from caixa_nfse.caixa.services.importador import ImportadorMovimentos
        from caixa_nfse.core.models import ConexaoExterna

        logger = logging.getLogger(__name__)
        self.object = self.get_object()
        abertura = self.object
        action = request.POST.get("action", "buscar")

        if action == "importar":
            return self._importar_selecionados(request, abertura)

        # Step 1: Buscar (execute SQL and return preview)
        pairs_raw = request.POST.getlist("conexao_rotina_pairs")
        data_inicio = request.POST.get("data_inicio")
        data_fim = request.POST.get("data_fim")

        if not pairs_raw or not data_inicio or not data_fim:
            return HttpResponse(
                '<div class="p-4 text-red-500 text-sm">'
                "Preencha todos os campos: conexão, rotinas e período.</div>"
            )

        # Parse pairs into {conexao_id: [rotina_ids]}
        from collections import defaultdict

        conexao_rotinas = defaultdict(list)
        for pair in pairs_raw:
            parts = pair.split(":")
            if len(parts) == 2:
                conexao_rotinas[parts[0]].append(parts[1])

        if not conexao_rotinas:
            return HttpResponse(
                '<div class="p-4 text-red-500 text-sm">'
                "Selecione ao menos uma conexão e rotina.</div>"
            )

        try:
            from caixa_nfse.caixa.models import MovimentoImportado

            all_logs = []
            preview_rows = []

            for con_id, rot_ids in conexao_rotinas.items():
                conexao = ConexaoExterna.objects.get(pk=con_id, tenant=request.user.tenant)
                rotinas = Rotina.objects.filter(pk__in=rot_ids, ativo=True)

                resultados = ImportadorMovimentos.executar_rotinas(
                    conexao, rotinas, data_inicio, data_fim
                )

                # Duplicate detection per conexao
                existing_by_rotina = {}
                for rot in rotinas:
                    existing_by_rotina[str(rot.pk)] = set(
                        MovimentoImportado.objects.filter(
                            tenant=request.user.tenant,
                            conexao__sistema=conexao.sistema,
                            rotina=rot,
                        )
                        .exclude(protocolo="")
                        .values_list("protocolo", flat=True)
                    )

                for rotina, headers, rows, logs in resultados:
                    all_logs.extend(logs)
                    if headers and rows:
                        for row in rows:
                            mapped = ImportadorMovimentos.mapear_colunas(rotina, headers, row)
                            if mapped:
                                mapped["meta_conexao_id"] = str(conexao.pk)
                                mapped["meta_rotina_id"] = str(rotina.pk)
                                mapped["meta_origem"] = f"{conexao.sistema} - {rotina.nome}"
                                mapped["meta_raw_headers"] = json.dumps(headers)
                                mapped["meta_raw_row"] = json.dumps(
                                    [str(v) if v is not None else "" for v in row]
                                )
                                protocolo = str(mapped.get("protocolo", "") or "").strip()
                                existing = existing_by_rotina.get(str(rotina.pk), set())
                                mapped["meta_duplicado"] = bool(protocolo and protocolo in existing)
                                preview_rows.append(mapped)

            if not preview_rows:
                html = render_to_string(
                    "caixa/partials/importados_results.html",
                    {
                        "total_importados": 0,
                        "total_rows": 0,
                        "logs": all_logs,
                        "abertura": abertura,
                    },
                    request=request,
                )
                return HttpResponse(html)

            html = render_to_string(
                "caixa/partials/importados_preview.html",
                {
                    "preview_rows": preview_rows,
                    "logs": all_logs,
                    "abertura": abertura,
                },
                request=request,
            )
            return HttpResponse(html)

        except Exception:
            logger.exception("Erro ao buscar movimentos")
            return HttpResponse(
                '<div class="p-4 text-red-500 text-sm">'
                "Erro ao conectar ou executar rotinas. Verifique a conexão e tente novamente.</div>"
            )

    def _importar_selecionados(self, request, abertura):
        """Step 2: Import only selected rows."""
        import json
        import logging

        from django.http import HttpResponse
        from django.template.loader import render_to_string

        from caixa_nfse.backoffice.models import Rotina
        from caixa_nfse.caixa.services.importador import ImportadorMovimentos
        from caixa_nfse.core.models import ConexaoExterna

        logger = logging.getLogger(__name__)
        selected = request.POST.getlist("selected_rows")

        if not selected:
            return HttpResponse(
                '<div class="p-4 text-amber-500 text-sm">'
                "Nenhum item selecionado para importação.</div>"
            )

        try:
            conexao_cache = {}
            total_importados = 0
            total_duplicados = 0

            for idx in selected:
                conexao_id = request.POST.get(f"conexao_id_{idx}")
                rotina_id = request.POST.get(f"rotina_id_{idx}")
                raw_headers = request.POST.get(f"raw_headers_{idx}")
                raw_row = request.POST.get(f"raw_row_{idx}")

                if not all([conexao_id, rotina_id, raw_headers, raw_row]):
                    continue

                if conexao_id not in conexao_cache:
                    conexao_cache[conexao_id] = ConexaoExterna.objects.get(
                        pk=conexao_id, tenant=request.user.tenant
                    )
                conexao = conexao_cache[conexao_id]
                rotina = Rotina.objects.get(pk=rotina_id, ativo=True)
                headers = json.loads(raw_headers)
                row = json.loads(raw_row)

                created, skipped = ImportadorMovimentos.salvar_importacao(
                    abertura, conexao, rotina, headers, [row], request.user
                )
                total_importados += created
                total_duplicados += skipped

            html = render_to_string(
                "caixa/partials/importados_results.html",
                {
                    "total_importados": total_importados,
                    "total_duplicados": total_duplicados,
                    "total_rows": len(selected),
                    "logs": [],
                    "abertura": abertura,
                },
                request=request,
            )
            return HttpResponse(html)

        except Exception:
            logger.exception("Erro ao importar selecionados")
            return HttpResponse(
                '<div class="p-4 text-red-500 text-sm">'
                "Erro ao importar registros selecionados.</div>"
            )


class ListaImportadosView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """List pending imported movements for an abertura."""

    model = None
    context_object_name = "importados"

    def get_template_names(self):
        if self.request.headers.get("HX-Request"):
            return ["caixa/partials/importados_list.html"]
        return ["caixa/importados_page.html"]

    def test_func(self):
        return self.request.user.pode_operar_caixa

    def get_queryset(self):
        from caixa_nfse.caixa.models import MovimentoImportado

        return MovimentoImportado.objects.filter(
            abertura_id=self.kwargs["pk"],
            tenant=self.request.user.tenant,
            confirmado=False,
        ).select_related("rotina", "conexao")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["abertura"] = get_object_or_404(
            AberturaCaixa,
            pk=self.kwargs["pk"],
            tenant=self.request.user.tenant,
        )
        from caixa_nfse.core.models import FormaPagamento

        context["formas_pagamento"] = FormaPagamento.objects.filter(
            tenant=self.request.user.tenant, ativo=True
        )
        return context


class ConfirmarImportadosView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """Confirm selected imported movements and migrate to MovimentoCaixa."""

    model = AberturaCaixa

    def test_func(self):
        return self.request.user.pode_operar_caixa

    def get_queryset(self):
        return AberturaCaixa.objects.filter(tenant=self.request.user.tenant, fechado=False)

    def post(self, request, *args, **kwargs):
        from django.http import HttpResponse

        from caixa_nfse.caixa.models import TipoMovimento
        from caixa_nfse.caixa.services.importador import ImportadorMovimentos
        from caixa_nfse.core.models import FormaPagamento

        self.object = self.get_object()
        abertura = self.object

        ids = request.POST.getlist("importado_ids")
        forma_pagamento_id = request.POST.get("forma_pagamento_id")
        tipo = request.POST.get("tipo", TipoMovimento.ENTRADA)

        if not ids or not forma_pagamento_id:
            return HttpResponse(
                '<div class="p-3 text-red-500 text-sm">'
                "Selecione ao menos um item e a forma de pagamento.</div>"
            )

        try:
            forma_pagamento = FormaPagamento.objects.get(
                pk=forma_pagamento_id, tenant=request.user.tenant
            )
            count = ImportadorMovimentos.confirmar_movimentos(
                ids, abertura, forma_pagamento, tipo, request.user
            )

            response = HttpResponse()
            response["HX-Refresh"] = "true"
            messages.success(request, f"{count} movimento(s) confirmado(s) com sucesso!")
            return response

        except Exception:
            import logging

            logging.getLogger(__name__).exception("Erro ao confirmar importados")
            return HttpResponse(
                '<div class="p-3 text-red-500 text-sm">Erro ao confirmar movimentos.</div>'
            )


class ExcluirImportadosView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """Delete selected imported movements (discard)."""

    model = AberturaCaixa

    def test_func(self):
        return self.request.user.pode_operar_caixa

    def get_queryset(self):
        return AberturaCaixa.objects.filter(tenant=self.request.user.tenant, fechado=False)

    def post(self, request, *args, **kwargs):
        from django.http import HttpResponse

        from caixa_nfse.caixa.models import MovimentoImportado

        self.object = self.get_object()

        ids = request.POST.getlist("importado_ids")
        if not ids:
            return HttpResponse(
                '<div class="p-3 text-red-500 text-sm">'
                "Selecione ao menos um item para excluir.</div>"
            )

        deleted, _ = MovimentoImportado.objects.filter(
            pk__in=ids,
            abertura=self.object,
            tenant=request.user.tenant,
            confirmado=False,
        ).delete()

        response = HttpResponse()
        response["HX-Refresh"] = "true"
        messages.success(request, f"{deleted} item(ns) excluído(s).")
        return response
