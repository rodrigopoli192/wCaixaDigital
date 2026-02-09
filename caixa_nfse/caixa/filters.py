"""
Caixa filters (django-filter).
"""

import django_filters
from django.utils.translation import gettext_lazy as _

from .models import Caixa, MovimentoCaixa, StatusCaixa, TipoMovimento


class CaixaFilter(django_filters.FilterSet):
    """Filter for Caixa."""

    identificador = django_filters.CharFilter(lookup_expr="icontains")
    status = django_filters.ChoiceFilter(choices=StatusCaixa.choices)

    class Meta:
        model = Caixa
        fields = ["identificador", "tipo", "status", "ativo"]


class MovimentoFilter(django_filters.FilterSet):
    """Filter for MovimentoCaixa."""

    tipo = django_filters.ChoiceFilter(choices=TipoMovimento.choices)
    protocolo = django_filters.CharFilter(lookup_expr="icontains", label=_("Protocolo"))
    data_hora = django_filters.DateFromToRangeFilter(
        label=_("Período"),
        widget=django_filters.widgets.RangeWidget(attrs={"type": "date"}),
    )
    valor_min = django_filters.NumberFilter(field_name="valor", lookup_expr="gte")
    valor_max = django_filters.NumberFilter(field_name="valor", lookup_expr="lte")

    class Meta:
        model = MovimentoCaixa
        fields = ["tipo", "forma_pagamento", "protocolo"]
