from django.contrib import admin

from .models import Cliente


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ["razao_social", "cpf_cnpj", "tipo_pessoa", "cidade", "uf", "ativo"]
    list_filter = ["tipo_pessoa", "ativo", "uf", "tenant"]
    search_fields = ["razao_social", "nome_fantasia", "cpf_cnpj", "email"]
    readonly_fields = ["id", "created_at", "updated_at", "cpf_cnpj_hash"]
