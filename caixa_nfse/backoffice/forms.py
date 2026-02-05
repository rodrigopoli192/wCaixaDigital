from django import forms
from django.contrib.auth import get_user_model
from django.db import transaction

from caixa_nfse.core.models import Tenant

User = get_user_model()


class TenantOnboardingForm(forms.ModelForm):
    """
    Unified form to create a Tenant and its first Admin User.
    """

    # Admin User Fields
    admin_name = forms.CharField(label="Nome do Responsável", max_length=150)
    admin_email = forms.EmailField(
        label="E-mail (Login)", help_text="Será o login do administrador."
    )
    admin_password = forms.CharField(
        label="Senha Inicial",
        widget=forms.PasswordInput,
        help_text="Senha temporária para o primeiro acesso.",
    )

    class Meta:
        model = Tenant
        fields = [
            "razao_social",
            "nome_fantasia",
            "cnpj",
            "cidade",
            "uf",
            "regime_tributario",
            "logradouro",
            "numero",
            "bairro",
            "cep",
            "telefone",
        ]

    @transaction.atomic
    def save(self, commit=True):
        # 1. Create Tenant
        tenant = super().save(commit=False)
        tenant.ativo = True  # Auto-activate
        if commit:
            tenant.save()

        # 2. Create Admin User
        User.objects.create_user(
            email=self.cleaned_data["admin_email"],
            password=self.cleaned_data["admin_password"],
            first_name=self.cleaned_data["admin_name"].split()[0],
            last_name=" ".join(self.cleaned_data["admin_name"].split()[1:]),
            tenant=tenant,
            # Permissions - Full Access
            pode_operar_caixa=True,
            pode_emitir_nfse=True,
            pode_cancelar_nfse=True,
            pode_aprovar_fechamento=True,
            pode_exportar_dados=True,
        )

        return tenant


class TenantUpdateForm(forms.ModelForm):
    """
    Form to update Tenant details.
    """

    class Meta:
        model = Tenant
        fields = [
            "razao_social",
            "nome_fantasia",
            "cnpj",
            "cidade",
            "uf",
            "regime_tributario",
            "logradouro",
            "numero",
            "bairro",
            "cep",
            "telefone",
            "ativo",
        ]
