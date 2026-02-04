from django.contrib import admin

from .models import LivroFiscalServicos


@admin.register(LivroFiscalServicos)
class LivroFiscalServicosAdmin(admin.ModelAdmin):
    list_display = [
        "competencia",
        "municipio_ibge",
        "total_notas",
        "valor_servicos",
        "valor_iss",
        "fechado",
    ]
    list_filter = ["fechado", "competencia", "tenant"]
    date_hierarchy = "competencia"
