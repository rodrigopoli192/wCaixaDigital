"""
Caixa forms.
"""

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Column, Layout, Row, Submit
from django import forms

from .models import AberturaCaixa, FechamentoCaixa, MovimentoCaixa


class AbrirCaixaForm(forms.ModelForm):
    """Form para abertura de caixa."""

    class Meta:
        model = AberturaCaixa
        fields = ["saldo_abertura", "fundo_troco", "observacao"]
        widgets = {
            "observacao": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column("saldo_abertura", css_class="col-md-6"),
                Column("fundo_troco", css_class="col-md-6"),
            ),
            "observacao",
            Submit("submit", "Abrir Caixa", css_class="btn-primary"),
        )


class MovimentoCaixaForm(forms.ModelForm):
    """Form para movimento de caixa."""

    class Meta:
        model = MovimentoCaixa
        fields = ["tipo", "forma_pagamento", "valor", "descricao", "cliente"]
        widgets = {
            "descricao": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)

        if tenant:
            self.fields["forma_pagamento"].queryset = self.fields[
                "forma_pagamento"
            ].queryset.filter(tenant=tenant, ativo=True)
            self.fields["cliente"].queryset = self.fields["cliente"].queryset.filter(tenant=tenant)

        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column("tipo", css_class="col-md-4"),
                Column("forma_pagamento", css_class="col-md-4"),
                Column("valor", css_class="col-md-4"),
            ),
            "cliente",
            "descricao",
            Submit("submit", "Registrar Movimento", css_class="btn-primary"),
        )


class FechamentoCaixaForm(forms.ModelForm):
    """Form para fechamento de caixa."""

    class Meta:
        model = FechamentoCaixa
        fields = ["saldo_informado", "justificativa_diferenca"]
        widgets = {
            "justificativa_diferenca": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            "saldo_informado",
            "justificativa_diferenca",
            Submit("submit", "Fechar Caixa", css_class="btn-warning"),
        )

    def clean(self):
        cleaned_data = super().clean()
        return cleaned_data
