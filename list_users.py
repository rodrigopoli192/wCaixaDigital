import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "caixa_nfse.settings.base")
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

print("\n--- SUPERUSERS (PLATAFORMA) ---")
for u in User.objects.filter(is_superuser=True):
    print(f"Email: {u.email} | Nome: {u.get_full_name()}")

print("\n--- TENANT ADMINS E USERS ---")
for u in User.objects.filter(is_superuser=False).order_by("tenant__razao_social"):
    tenant_name = u.tenant.razao_social if u.tenant else "SEM TENANT"
    is_admin = "SIM" if u.pode_aprovar_fechamento else "NÃO"
    print(
        f"Email: {u.email} | Nome: {u.get_full_name()} | Tenant: {tenant_name} | Admin do Tenant: {is_admin}"
    )
