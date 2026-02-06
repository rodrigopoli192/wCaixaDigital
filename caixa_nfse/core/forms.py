"""
Core forms.
"""

from django import forms

from .models import ConexaoExterna, FormaPagamento


class FormaPagamentoForm(forms.ModelForm):
    """Form para cadastro/edição de formas de pagamento."""

    class Meta:
        model = FormaPagamento
        fields = [
            "nome",
            "tipo",
            "taxa_percentual",
            "prazo_recebimento",
            "conta_contabil",
            "ativo",
        ]
        widgets = {
            "nome": forms.TextInput(attrs={"placeholder": "Ex: PIX, Cartão Visa..."}),
            "taxa_percentual": forms.NumberInput(
                attrs={"step": "0.01", "min": "0", "max": "100", "placeholder": "0.00"}
            ),
            "prazo_recebimento": forms.NumberInput(attrs={"min": "0", "placeholder": "0"}),
            "conta_contabil": forms.TextInput(attrs={"placeholder": "Ex: 1.1.01.001"}),
        }
        help_texts = {
            "taxa_percentual": "Taxa cobrada pela operadora (ex: 1.99 = 1.99%)",
            "prazo_recebimento": "Dias para recebimento após a venda",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set ativo default to True for new records
        if not self.instance.pk:
            self.fields["ativo"].initial = True


class ConexaoExternaForm(forms.ModelForm):
    """Form para cadastro de conexões externas."""

    class Meta:
        model = ConexaoExterna
        fields = [
            "sistema",
            "tipo_conexao",
            "host",
            "porta",
            "database",
            "usuario",
            "senha",
            "charset",
            "instancia",
            "ativo",
        ]
        widgets = {
            "senha": forms.PasswordInput(render_value=True),
        }
