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

    # Campos de conferência (não salvos no model diretamente, mas usados para calcular saldo_informado)
    valor_dinheiro = forms.DecimalField(
        label="Dinheiro", required=False, initial=0, decimal_places=2, max_digits=14
    )
    valor_cartao_debito = forms.DecimalField(
        label="Cartão Débito", required=False, initial=0, decimal_places=2, max_digits=14
    )
    valor_cartao_credito = forms.DecimalField(
        label="Cartão Crédito", required=False, initial=0, decimal_places=2, max_digits=14
    )
    valor_pix = forms.DecimalField(
        label="PIX", required=False, initial=0, decimal_places=2, max_digits=14
    )
    valor_outros = forms.DecimalField(
        label="Outros", required=False, initial=0, decimal_places=2, max_digits=14
    )
    observacoes = forms.CharField(
        label="Observações", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )

    class Meta:
        model = FechamentoCaixa
        fields = ["saldo_informado", "justificativa_diferenca"]
        widgets = {
            "justificativa_diferenca": forms.Textarea(attrs={"rows": 3}),
            "saldo_informado": forms.HiddenInput(),  # Calculado automaticamente
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            "saldo_informado",
            "justificativa_diferenca",
            Submit("submit", "Fechar Caixa", css_class="btn-warning"),
        )
        # Campos opcionais para UI
        self.fields["valor_dinheiro"].widget.attrs.update({"class": "valor-input"})
        self.fields["valor_cartao_debito"].widget.attrs.update({"class": "valor-input"})
        self.fields["valor_cartao_credito"].widget.attrs.update({"class": "valor-input"})
        self.fields["valor_pix"].widget.attrs.update({"class": "valor-input"})
        self.fields["valor_outros"].widget.attrs.update({"class": "valor-input"})

    def clean(self):
        cleaned_data = super().clean()
        # Soma os valores informados para compor o saldo_informado
        total = sum(
            [
                cleaned_data.get("valor_dinheiro") or 0,
                cleaned_data.get("valor_cartao_debito") or 0,
                cleaned_data.get("valor_cartao_credito") or 0,
                cleaned_data.get("valor_pix") or 0,
                cleaned_data.get("valor_outros") or 0,
            ]
        )

        # Override saldo_informado with calculated total
        cleaned_data["saldo_informado"] = total

        # Se os campos vierem vazios do post (ex: js calculation fail), garante que o saldo_informado seja respeitado se preenchido hidden
        # Mas aqui preferimos confiar na soma dos inputs explícitos

        return cleaned_data
