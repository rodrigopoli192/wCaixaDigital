import django_filters

from .models import Cliente, TipoPessoa


class ClienteFilter(django_filters.FilterSet):
    razao_social = django_filters.CharFilter(lookup_expr="icontains")
    cpf_cnpj = django_filters.CharFilter(lookup_expr="icontains")
    tipo_pessoa = django_filters.ChoiceFilter(choices=TipoPessoa.choices)
    cidade = django_filters.CharFilter(lookup_expr="icontains")
    cadastro_completo = django_filters.BooleanFilter()

    class Meta:
        model = Cliente
        fields = ["tipo_pessoa", "ativo", "uf", "cadastro_completo"]
