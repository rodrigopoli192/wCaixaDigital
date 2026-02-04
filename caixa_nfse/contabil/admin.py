from django.contrib import admin

from .models import CentroCusto, LancamentoContabil, PartidaLancamento, PlanoContas


class PartidaInline(admin.TabularInline):
    model = PartidaLancamento
    extra = 2


@admin.register(PlanoContas)
class PlanoContasAdmin(admin.ModelAdmin):
    list_display = ["codigo", "descricao", "tipo", "natureza", "nivel", "permite_lancamento"]
    list_filter = ["tipo", "natureza", "nivel", "tenant"]
    search_fields = ["codigo", "descricao"]


@admin.register(CentroCusto)
class CentroCustoAdmin(admin.ModelAdmin):
    list_display = ["codigo", "descricao", "tenant", "ativo"]
    list_filter = ["ativo", "tenant"]


@admin.register(LancamentoContabil)
class LancamentoContabilAdmin(admin.ModelAdmin):
    list_display = ["data_lancamento", "data_competencia", "historico", "valor_total", "estornado"]
    list_filter = ["data_lancamento", "estornado", "tenant"]
    search_fields = ["historico", "numero_documento"]
    date_hierarchy = "data_lancamento"
    inlines = [PartidaInline]
