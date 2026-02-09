"""
Caixa tables (django-tables2).
"""

import django_tables2 as tables
from django.utils.html import format_html

from .models import Caixa, MovimentoCaixa


class CaixaTable(tables.Table):
    """Table for Caixa list."""

    identificador = tables.Column(linkify=True)
    status = tables.Column()
    operador_atual = tables.Column(verbose_name="Operador")
    saldo_atual = tables.Column(verbose_name="Saldo")
    acoes = tables.TemplateColumn(
        template_name="caixa/_caixa_acoes.html",
        verbose_name="Ações",
        orderable=False,
    )

    class Meta:
        model = Caixa
        fields = ["identificador", "tipo", "status", "operador_atual", "saldo_atual"]
        attrs = {"class": "table table-striped table-hover"}
        row_attrs = {"class": lambda record: "table-success" if record.esta_aberto else ""}


class MovimentoTable(tables.Table):
    """Table for MovimentoCaixa list."""

    data_hora = tables.DateTimeColumn(format="d/m/Y H:i")
    tipo = tables.Column()
    forma_pagamento = tables.Column()
    valor = tables.Column()
    protocolo = tables.Column(verbose_name="Protocolo")
    emolumento = tables.Column(verbose_name="Emolumento")
    valor_total_taxas = tables.Column(
        verbose_name="Total Taxas",
        accessor="valor_total_taxas",
        orderable=False,
    )
    descricao = tables.Column()

    class Meta:
        model = MovimentoCaixa
        fields = [
            "data_hora",
            "tipo",
            "forma_pagamento",
            "valor",
            "protocolo",
            "emolumento",
            "valor_total_taxas",
            "descricao",
        ]
        attrs = {"class": "table table-striped table-hover table-sm"}
        row_attrs = {
            "class": lambda record: "table-success" if record.is_entrada else "table-danger"
        }

    def render_valor(self, value, record):
        """Format valor with color."""
        color = "text-success" if record.is_entrada else "text-danger"
        prefix = "+" if record.is_entrada else "-"
        return format_html(
            '<span class="{}">{} R$ {}</span>',
            color,
            prefix,
            f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
        )

    def render_emolumento(self, value):
        """Format emolumento as BRL."""
        if not value:
            return "—"
        return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    def render_valor_total_taxas(self, value):
        """Format total taxas as BRL."""
        if not value:
            return "—"
        return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
