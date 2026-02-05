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


class TenantUserForm(forms.ModelForm):
    """
    Form for creating/editing users within a Tenant (backoffice).
    """

    password = forms.CharField(
        label="Senha",
        widget=forms.PasswordInput,
        required=False,
        help_text="Deixe em branco para manter a senha atual (edição).",
    )

    class Meta:
        model = User
        fields = [
            "email",
            "first_name",
            "last_name",
            "cargo",
            "telefone",
            "is_active",
            "pode_operar_caixa",
            "pode_emitir_nfse",
            "pode_cancelar_nfse",
            "pode_aprovar_fechamento",
            "pode_exportar_dados",
        ]

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        # Password required for new users
        if not self.instance.pk:
            self.fields["password"].required = True
            self.fields["password"].help_text = "Senha inicial obrigatória."

    def save(self, commit=True):
        user = super().save(commit=False)
        user.tenant = self.tenant

        password = self.cleaned_data.get("password")
        if password:
            user.set_password(password)

        if commit:
            user.save()
        return user
