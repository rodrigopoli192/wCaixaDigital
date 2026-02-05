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

    emitir_nfse = forms.BooleanField(
        label="Emitir NFS-e automaticamente",
        required=False,
        initial=False,
        help_text="Gera a nota fiscal eletrônica após o registro",
    )

    class Meta:
        model = MovimentoCaixa
        fields = ["tipo", "forma_pagamento", "valor", "descricao", "cliente"]
        widgets = {
            "descricao": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)

        # Set default value for "tipo" to ENTRADA
        self.fields["tipo"].initial = "ENTRADA"

        if tenant:
            self.fields["forma_pagamento"].queryset = self.fields[
                "forma_pagamento"
            ].queryset.filter(tenant=tenant, ativo=True)
            self.fields["cliente"].queryset = self.fields["cliente"].queryset.filter(tenant=tenant)

        # Override label_from_instance to show only the name (não "Nome (Tipo)")
        self.fields["forma_pagamento"].label_from_instance = lambda obj: obj.nome

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

    observacoes = forms.CharField(
        label="Observações", required=False, widget=forms.Textarea(attrs={"rows": 3})
    )

    class Meta:
        model = FechamentoCaixa
        fields = ["saldo_informado", "justificativa_diferenca"]
        widgets = {
            "justificativa_diferenca": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, saldo_sistema=None, **kwargs):
        self.saldo_sistema = saldo_sistema
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            "saldo_informado",
            "justificativa_diferenca",
            Submit("submit", "Fechar Caixa", css_class="btn-warning"),
        )
        self.fields["saldo_informado"].widget.attrs.update(
            {"class": "valor-input text-xl font-bold text-center"}
        )

    def clean(self):
        cleaned_data = super().clean()
        saldo_informado = cleaned_data.get("saldo_informado")
        justificativa = cleaned_data.get("justificativa_diferenca")

        if saldo_informado is not None and self.saldo_sistema is not None:
            diferenca = saldo_informado - self.saldo_sistema

            # Se houver diferença maior que 1 centavo (abs), exige justificativa
            if abs(diferenca) > 0.01 and not justificativa:
                self.add_error(
                    "justificativa_diferenca",
                    f"Justificativa obrigatória pois há uma diferença de R$ {diferenca:,.2f}.",
                )

        return cleaned_data
