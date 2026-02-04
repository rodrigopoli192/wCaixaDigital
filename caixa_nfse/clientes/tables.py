import django_tables2 as tables

from .models import Cliente


class ClienteTable(tables.Table):
    razao_social = tables.Column(linkify=True)
    acoes = tables.TemplateColumn(
        template_name="clientes/_cliente_acoes.html",
        verbose_name="Ações",
        orderable=False,
    )

    class Meta:
        model = Cliente
        fields = ["razao_social", "cpf_cnpj", "tipo_pessoa", "cidade", "uf", "ativo"]
        attrs = {"class": "table table-striped table-hover"}
