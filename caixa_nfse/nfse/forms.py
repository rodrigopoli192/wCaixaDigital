"""
NFS-e forms — styled ModelForm for create/update.
"""

from django import forms

from .models import NotaFiscalServico

_INPUT = (
    "w-full bg-slate-50 dark:bg-background-dark border "
    "border-slate-200 dark:border-border-dark rounded-lg px-4 py-2.5 text-sm "
    "text-slate-900 dark:text-slate-100 placeholder:text-slate-400 "
    "dark:placeholder:text-slate-500 "
    "focus:ring-2 focus:ring-primary/40 focus:border-primary "
    "transition-all outline-none"
)

_INPUT_MONEY = (
    "w-full bg-slate-50 dark:bg-background-dark border "
    "border-slate-200 dark:border-border-dark rounded-lg pl-10 pr-4 py-2.5 text-sm "
    "text-slate-900 dark:text-slate-100 placeholder:text-slate-400 "
    "dark:placeholder:text-slate-500 "
    "focus:ring-2 focus:ring-primary/40 focus:border-primary "
    "transition-all outline-none"
)

_SELECT = (
    "w-full bg-slate-50 dark:bg-background-dark border "
    "border-slate-200 dark:border-border-dark rounded-lg px-4 py-2.5 text-sm "
    "text-slate-900 dark:text-slate-100 "
    "focus:ring-2 focus:ring-primary/40 focus:border-primary "
    "transition-all outline-none appearance-none cursor-pointer "
    "bg-[url('data:image/svg+xml;charset=utf-8,"
    "<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 20 20%22 fill=%22%2394a3b8%22>"
    "<path fill-rule=%22evenodd%22 d=%22M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a"
    ".75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z%22 "
    "clip-rule=%22evenodd%22/></svg>')] "
    "bg-[length:1.25rem] bg-[right_0.5rem_center] bg-no-repeat pr-10"
)

_TEXTAREA = (
    "w-full bg-slate-50 dark:bg-background-dark border "
    "border-slate-200 dark:border-border-dark rounded-lg px-4 py-2.5 text-sm "
    "text-slate-900 dark:text-slate-100 placeholder:text-slate-400 "
    "dark:placeholder:text-slate-500 "
    "focus:ring-2 focus:ring-primary/40 focus:border-primary "
    "transition-all outline-none resize-none"
)

_CHECKBOX = (
    "w-5 h-5 rounded border-slate-300 dark:border-border-dark "
    "text-primary focus:ring-primary/40 bg-slate-50 dark:bg-background-dark "
    "cursor-pointer"
)


class NFSeForm(forms.ModelForm):
    class Meta:
        model = NotaFiscalServico
        fields = [
            "cliente",
            "servico",
            "discriminacao",
            "competencia",
            "valor_servicos",
            "valor_deducoes",
            "valor_pis",
            "valor_cofins",
            "valor_inss",
            "valor_ir",
            "valor_csll",
            "aliquota_iss",
            "iss_retido",
            "local_prestacao_ibge",
        ]
        widgets = {
            "cliente": forms.Select(
                attrs={
                    "class": _SELECT,
                    "id": "id_cliente",
                }
            ),
            "servico": forms.Select(
                attrs={
                    "class": _SELECT,
                    "id": "id_servico",
                }
            ),
            "discriminacao": forms.Textarea(
                attrs={
                    "class": _TEXTAREA,
                    "rows": 4,
                    "placeholder": "Descreva detalhadamente os serviços prestados...",
                    "id": "id_discriminacao",
                }
            ),
            "competencia": forms.DateInput(
                attrs={
                    "class": _INPUT,
                    "type": "month",
                    "id": "id_competencia",
                }
            ),
            "valor_servicos": forms.NumberInput(
                attrs={
                    "class": _INPUT_MONEY,
                    "placeholder": "0,00",
                    "step": "0.01",
                    "min": "0.01",
                    "id": "id_valor_servicos",
                }
            ),
            "valor_deducoes": forms.NumberInput(
                attrs={
                    "class": _INPUT_MONEY,
                    "placeholder": "0,00",
                    "step": "0.01",
                    "min": "0",
                    "id": "id_valor_deducoes",
                }
            ),
            "valor_pis": forms.NumberInput(
                attrs={
                    "class": _INPUT_MONEY,
                    "placeholder": "0,00",
                    "step": "0.01",
                    "min": "0",
                    "id": "id_valor_pis",
                }
            ),
            "valor_cofins": forms.NumberInput(
                attrs={
                    "class": _INPUT_MONEY,
                    "placeholder": "0,00",
                    "step": "0.01",
                    "min": "0",
                    "id": "id_valor_cofins",
                }
            ),
            "valor_inss": forms.NumberInput(
                attrs={
                    "class": _INPUT_MONEY,
                    "placeholder": "0,00",
                    "step": "0.01",
                    "min": "0",
                    "id": "id_valor_inss",
                }
            ),
            "valor_ir": forms.NumberInput(
                attrs={
                    "class": _INPUT_MONEY,
                    "placeholder": "0,00",
                    "step": "0.01",
                    "min": "0",
                    "id": "id_valor_ir",
                }
            ),
            "valor_csll": forms.NumberInput(
                attrs={
                    "class": _INPUT_MONEY,
                    "placeholder": "0,00",
                    "step": "0.01",
                    "min": "0",
                    "id": "id_valor_csll",
                }
            ),
            "aliquota_iss": forms.NumberInput(
                attrs={
                    "class": _INPUT,
                    "placeholder": "5,00",
                    "step": "0.01",
                    "min": "0",
                    "max": "100",
                    "id": "id_aliquota_iss",
                }
            ),
            "iss_retido": forms.CheckboxInput(
                attrs={
                    "class": _CHECKBOX,
                    "id": "id_iss_retido",
                }
            ),
            "local_prestacao_ibge": forms.TextInput(
                attrs={
                    "class": _INPUT,
                    "placeholder": "Ex: 3550308 (São Paulo)",
                    "id": "id_local_prestacao_ibge",
                }
            ),
        }

    def clean_competencia(self):
        """Accept YYYY-MM from type=month and convert to first day of month."""
        import datetime

        value = self.cleaned_data.get("competencia")
        if isinstance(value, datetime.date):
            return value
        raw = self.data.get("competencia", "")
        if raw and len(raw) == 7:  # YYYY-MM
            try:
                return datetime.date.fromisoformat(f"{raw}-01")
            except ValueError:
                pass
        return value
