from crispy_forms.helper import FormHelper
from crispy_forms.layout import Column, Fieldset, Layout, Row, Submit
from django import forms

from .models import Cliente


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = [
            "tipo_pessoa",
            "cpf_cnpj",
            "razao_social",
            "nome_fantasia",
            "inscricao_municipal",
            "inscricao_estadual",
            "email",
            "telefone",
            "logradouro",
            "numero",
            "complemento",
            "bairro",
            "cidade",
            "uf",
            "cep",
            "codigo_ibge",
            "consentimento_lgpd",
            "ativo",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset(
                "Identificação",
                Row(
                    Column("tipo_pessoa", css_class="col-md-3"),
                    Column("cpf_cnpj", css_class="col-md-4"),
                    Column("inscricao_municipal", css_class="col-md-5"),
                ),
                Row(
                    Column("razao_social", css_class="col-md-6"),
                    Column("nome_fantasia", css_class="col-md-6"),
                ),
            ),
            Fieldset(
                "Contato",
                Row(
                    Column("email", css_class="col-md-6"),
                    Column("telefone", css_class="col-md-6"),
                ),
            ),
            Fieldset(
                "Endereço",
                Row(
                    Column("logradouro", css_class="col-md-8"),
                    Column("numero", css_class="col-md-2"),
                    Column("complemento", css_class="col-md-2"),
                ),
                Row(
                    Column("bairro", css_class="col-md-4"),
                    Column("cidade", css_class="col-md-4"),
                    Column("uf", css_class="col-md-2"),
                    Column("cep", css_class="col-md-2"),
                ),
            ),
            Row(
                Column("consentimento_lgpd", css_class="col-md-6"),
                Column("ativo", css_class="col-md-6"),
            ),
            Submit("submit", "Salvar", css_class="btn-primary"),
        )
