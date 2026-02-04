"""
Caixa admin configuration.
"""

from django.contrib import admin
from django.utils.html import format_html

from .models import AberturaCaixa, Caixa, FechamentoCaixa, MovimentoCaixa


@admin.register(Caixa)
class CaixaAdmin(admin.ModelAdmin):
    """Admin for Caixa."""

    list_display = [
        "identificador",
        "tenant",
        "tipo",
        "status_badge",
        "operador_atual",
        "saldo_atual",
        "ativo",
    ]
    list_filter = ["tipo", "status", "ativo", "tenant"]
    search_fields = ["identificador"]
    readonly_fields = ["id", "created_at", "updated_at", "saldo_atual"]

    def status_badge(self, obj):
        colors = {
            "FECHADO": "secondary",
            "ABERTO": "success",
            "BLOQUEADO": "danger",
        }
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            colors.get(obj.status, "secondary"),
            obj.get_status_display(),
        )

    status_badge.short_description = "Status"


class MovimentoInline(admin.TabularInline):
    """Inline for MovimentoCaixa in AberturaCaixa."""

    model = MovimentoCaixa
    extra = 0
    readonly_fields = ["data_hora", "tipo", "forma_pagamento", "valor", "hash_registro"]
    can_delete = False
    show_change_link = True


@admin.register(AberturaCaixa)
class AberturaCaixaAdmin(admin.ModelAdmin):
    """Admin for AberturaCaixa."""

    list_display = ["caixa", "operador", "data_hora", "saldo_abertura", "fechado"]
    list_filter = ["fechado", "caixa__tenant"]
    search_fields = ["caixa__identificador", "operador__email"]
    readonly_fields = ["id", "created_at", "hash_registro", "hash_anterior"]
    inlines = [MovimentoInline]
    date_hierarchy = "data_hora"


@admin.register(MovimentoCaixa)
class MovimentoCaixaAdmin(admin.ModelAdmin):
    """Admin for MovimentoCaixa."""

    list_display = ["data_hora", "abertura", "tipo", "forma_pagamento", "valor"]
    list_filter = ["tipo", "forma_pagamento", "abertura__caixa__tenant"]
    search_fields = ["descricao"]
    readonly_fields = ["id", "created_at", "hash_registro", "hash_anterior"]
    date_hierarchy = "data_hora"


@admin.register(FechamentoCaixa)
class FechamentoCaixaAdmin(admin.ModelAdmin):
    """Admin for FechamentoCaixa."""

    list_display = [
        "abertura",
        "operador",
        "data_hora",
        "saldo_sistema",
        "saldo_informado",
        "diferenca_badge",
        "status",
    ]
    list_filter = ["status", "abertura__caixa__tenant"]
    readonly_fields = ["id", "created_at", "hash_registro", "diferenca"]
    date_hierarchy = "data_hora"

    def diferenca_badge(self, obj):
        if obj.diferenca == 0:
            return format_html('<span class="badge bg-success">OK</span>')
        color = "warning" if abs(obj.diferenca) <= 1 else "danger"
        return format_html(
            '<span class="badge bg-{}">R$ {}</span>',
            color,
            obj.diferenca,
        )

    diferenca_badge.short_description = "Diferença"
