from django.contrib import admin

from .models import EventoFiscal, NotaFiscalServico, ServicoMunicipal


@admin.register(ServicoMunicipal)
class ServicoMunicipalAdmin(admin.ModelAdmin):
    list_display = [
        "codigo_lc116",
        "codigo_municipal",
        "descricao",
        "aliquota_iss",
        "municipio_ibge",
    ]
    search_fields = ["codigo_lc116", "descricao"]
    list_filter = ["municipio_ibge"]


class EventoInline(admin.TabularInline):
    model = EventoFiscal
    extra = 0
    readonly_fields = ["tipo", "data_hora", "protocolo", "mensagem", "sucesso"]
    can_delete = False


@admin.register(NotaFiscalServico)
class NotaFiscalServicoAdmin(admin.ModelAdmin):
    list_display = [
        "numero_rps",
        "numero_nfse",
        "data_emissao",
        "cliente",
        "valor_servicos",
        "status",
    ]
    list_filter = ["status", "data_emissao", "tenant"]
    search_fields = ["numero_rps", "numero_nfse", "cliente__razao_social"]
    readonly_fields = ["id", "created_at", "base_calculo", "valor_iss", "valor_liquido"]
    date_hierarchy = "data_emissao"
    inlines = [EventoInline]


@admin.register(EventoFiscal)
class EventoFiscalAdmin(admin.ModelAdmin):
    list_display = ["nota", "tipo", "data_hora", "sucesso"]
    list_filter = ["tipo", "sucesso"]
    readonly_fields = ["id", "created_at", "data_hora"]
