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

    saldo_abertura = forms.CharField(
        label="Saldo de Abertura",
        widget=forms.TextInput(attrs={"class": "money-input", "inputmode": "decimal"}),
    )
    fundo_troco = forms.CharField(
        label="Fundo de Troco",
        widget=forms.TextInput(attrs={"class": "money-input", "inputmode": "decimal"}),
        required=False,
    )

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
        # Adicionar classes para formatação no frontend
        self.fields["saldo_abertura"].widget.attrs.update({"class": "money-input"})
        self.fields["fundo_troco"].widget.attrs.update({"class": "money-input"})

    def clean_saldo_abertura(self):
        """Converte valor BRL para Decimal."""
        return self._clean_money_field("saldo_abertura")

    def clean_fundo_troco(self):
        """Converte valor BRL para Decimal."""
        return self._clean_money_field("fundo_troco")

    def _clean_money_field(self, field_name):
        from decimal import Decimal, InvalidOperation

        valor = self.cleaned_data.get(field_name)
        if valor is None:
            return valor

        if isinstance(valor, Decimal):
            return valor

        # Remove formatação
        valor_str = str(valor).strip().replace("R$", "").replace(".", "").replace(",", ".")
        if not valor_str:
            return Decimal("0")

        try:
            return Decimal(valor_str)
        except InvalidOperation as e:
            raise forms.ValidationError("Valor inválido.") from e


class MovimentoCaixaForm(forms.ModelForm):
    """Form para movimento de caixa."""

    emitir_nfse = forms.BooleanField(
        label="Emitir NFS-e automaticamente",
        required=False,
        initial=False,
        help_text="Gera a nota fiscal eletrônica após o registro",
    )

    # Override: use CharField to handle Brazilian currency format (1.234,56)
    valor = forms.CharField(
        label="Valor",
        widget=forms.TextInput(
            attrs={
                "inputmode": "decimal",
                "autocomplete": "off",
                "placeholder": "0,00",
            }
        ),
    )

    # Tax fields as CharField for Brazilian currency mask
    TAXA_FIELD_NAMES = [
        "iss",
        "fundesp",
        "funesp",
        "estado",
        "fesemps",
        "funemp",
        "funcomp",
        "fepadsaj",
        "funproge",
        "fundepeg",
        "fundaf",
        "femal",
        "fecad",
        "emolumento",
        "taxa_judiciaria",
    ]

    class Meta:
        model = MovimentoCaixa
        fields = [
            "tipo",
            "forma_pagamento",
            "valor",
            "descricao",
            "cliente",
            "protocolo",
            "status_item",
            "quantidade",
            "iss",
            "fundesp",
            "funesp",
            "estado",
            "fesemps",
            "funemp",
            "funcomp",
            "fepadsaj",
            "funproge",
            "fundepeg",
            "fundaf",
            "femal",
            "fecad",
            "emolumento",
            "taxa_judiciaria",
        ]
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

        # Make tax fields not required
        for field_name in self.TAXA_FIELD_NAMES:
            self.fields[field_name].required = False

        # Make protocolo/status_item/quantidade not required
        for field_name in ["protocolo", "status_item", "quantidade"]:
            self.fields[field_name].required = False

        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column("tipo", css_class="col-md-4"),
                Column("forma_pagamento", css_class="col-md-4"),
                Column("valor", css_class="col-md-4"),
            ),
            "cliente",
            "descricao",
            Row(
                Column("protocolo", css_class="col-md-4"),
                Column("status_item", css_class="col-md-4"),
                Column("quantidade", css_class="col-md-4"),
            ),
            Row(
                Column("emolumento", css_class="col-md-6"),
                Column("taxa_judiciaria", css_class="col-md-6"),
            ),
            Row(
                Column("iss", css_class="col-md-3"),
                Column("fundesp", css_class="col-md-3"),
                Column("funesp", css_class="col-md-3"),
                Column("estado", css_class="col-md-3"),
            ),
            Row(
                Column("fesemps", css_class="col-md-3"),
                Column("funemp", css_class="col-md-3"),
                Column("funcomp", css_class="col-md-3"),
                Column("fepadsaj", css_class="col-md-3"),
            ),
            Row(
                Column("funproge", css_class="col-md-3"),
                Column("fundepeg", css_class="col-md-3"),
                Column("fundaf", css_class="col-md-3"),
                Column("femal", css_class="col-md-3"),
            ),
            Row(
                Column("fecad", css_class="col-md-4"),
            ),
            Submit("submit", "Registrar Movimento", css_class="btn-primary"),
        )

    def clean_valor(self):
        """Converte valor no formato brasileiro (1.234,56) para Decimal."""
        from decimal import Decimal, InvalidOperation

        valor = self.cleaned_data.get("valor")
        if valor is None:
            return valor

        # Se já for Decimal, retorna
        if isinstance(valor, Decimal):
            return valor

        # Converte para string e limpa
        valor_str = str(valor).strip()
        if not valor_str:
            return Decimal("0")

        # Remove R$ e espaços
        valor_str = valor_str.replace("R$", "").strip()

        # Converte formato brasileiro: 1.234,56 -> 1234.56
        valor_str = valor_str.replace(".", "").replace(",", ".")

        try:
            return Decimal(valor_str)
        except InvalidOperation as e:
            raise forms.ValidationError("Valor inválido. Use o formato: 1.234,56") from e

    def _parse_brl(self, value):
        """Parse Brazilian currency string to Decimal."""
        from decimal import Decimal, InvalidOperation

        if value is None or value == "":
            return Decimal("0.00")
        if isinstance(value, Decimal):
            return value

        valor_str = str(value).strip().replace("R$", "").strip()
        if not valor_str:
            return Decimal("0.00")

        valor_str = valor_str.replace(".", "").replace(",", ".")

        try:
            return Decimal(valor_str)
        except InvalidOperation:
            return Decimal("0.00")

    def clean(self):
        cleaned = super().clean()
        for field_name in self.TAXA_FIELD_NAMES:
            if field_name in cleaned:
                cleaned[field_name] = self._parse_brl(cleaned[field_name])
        return cleaned


class FechamentoCaixaForm(forms.ModelForm):
    """Form para fechamento de caixa."""

    observacoes = forms.CharField(
        label="Observações", required=False, widget=forms.Textarea(attrs={"rows": 3})
    )

    # Override to handle Brazilian currency format (1.234,56)
    saldo_informado = forms.CharField(
        label="Saldo Informado",
        widget=forms.TextInput(attrs={"inputmode": "decimal"}),
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

    def clean_saldo_informado(self):
        """Converte valor no formato brasileiro (1.234,56) para Decimal."""
        from decimal import Decimal, InvalidOperation

        valor = self.cleaned_data.get("saldo_informado")
        if not valor:
            raise forms.ValidationError("Este campo é obrigatório.")

        # Remove pontos de milhar e troca vírgula por ponto
        try:
            valor_limpo = valor.replace(".", "").replace(",", ".")
            return Decimal(valor_limpo)
        except (InvalidOperation, AttributeError) as err:
            raise forms.ValidationError("Informe um valor válido.") from err

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
