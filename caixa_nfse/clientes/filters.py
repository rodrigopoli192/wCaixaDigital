import django_filters

from .models import Cliente, TipoPessoa


class ClienteFilter(django_filters.FilterSet):
    razao_social = django_filters.CharFilter(lookup_expr="icontains")
    cpf_cnpj = django_filters.CharFilter(lookup_expr="icontains")
    tipo_pessoa = django_filters.ChoiceFilter(choices=TipoPessoa.choices)
    cidade = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = Cliente
        fields = ["tipo_pessoa", "ativo", "uf"]
