"""
Core admin configuration.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import FormaPagamento, Tenant, User


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    """Admin for Tenant model."""

    list_display = [
        "razao_social",
        "nome_fantasia",
        "cnpj",
        "cidade",
        "uf",
        "regime_tributario",
        "certificado_valido",
        "ativo",
    ]
    list_filter = ["uf", "regime_tributario", "ativo"]
    search_fields = ["razao_social", "nome_fantasia", "cnpj"]
    readonly_fields = ["id", "created_at", "updated_at"]

    fieldsets = (
        (
            _("Identificação"),
            {
                "fields": ("razao_social", "nome_fantasia", "cnpj"),
            },
        ),
        (
            _("Inscrições"),
            {
                "fields": ("inscricao_municipal", "inscricao_estadual", "regime_tributario"),
            },
        ),
        (
            _("Endereço"),
            {
                "fields": (
                    "logradouro",
                    "numero",
                    "complemento",
                    "bairro",
                    "cidade",
                    "uf",
                    "cep",
                    "codigo_ibge",
                ),
            },
        ),
        (
            _("Contato"),
            {
                "fields": ("telefone", "email"),
            },
        ),
        (
            _("Certificado Digital"),
            {
                "fields": ("certificado_digital", "certificado_senha", "certificado_validade"),
                "classes": ("collapse",),
            },
        ),
        (
            _("NFS-e"),
            {
                "fields": ("nfse_serie_padrao", "nfse_ultimo_rps"),
            },
        ),
        (
            _("Status"),
            {
                "fields": ("ativo",),
            },
        ),
        (
            _("Metadados"),
            {
                "fields": ("id", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin for custom User model."""

    list_display = [
        "email",
        "first_name",
        "last_name",
        "tenant",
        "is_active",
        "is_staff",
    ]
    list_filter = ["is_active", "is_staff", "tenant", "pode_operar_caixa"]
    search_fields = ["email", "first_name", "last_name", "cpf"]
    ordering = ["email"]

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            _("Informações Pessoais"),
            {
                "fields": ("first_name", "last_name", "cpf", "telefone", "cargo"),
            },
        ),
        (
            _("Empresa"),
            {
                "fields": ("tenant",),
            },
        ),
        (
            _("Permissões do Sistema"),
            {
                "fields": (
                    "pode_operar_caixa",
                    "pode_emitir_nfse",
                    "pode_cancelar_nfse",
                    "pode_aprovar_fechamento",
                    "pode_exportar_dados",
                ),
            },
        ),
        (
            _("Permissões Django"),
            {
                "fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions"),
                "classes": ("collapse",),
            },
        ),
        (
            _("Datas Importantes"),
            {
                "fields": ("last_login", "date_joined"),
                "classes": ("collapse",),
            },
        ),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2", "tenant"),
            },
        ),
    )


@admin.register(FormaPagamento)
class FormaPagamentoAdmin(admin.ModelAdmin):
    """Admin for FormaPagamento model."""

    list_display = [
        "nome",
        "tipo",
        "tenant",
        "taxa_percentual",
        "prazo_recebimento",
        "ativo",
    ]
    list_filter = ["tipo", "ativo", "tenant"]
    search_fields = ["nome"]
    readonly_fields = ["id", "created_at", "updated_at"]
