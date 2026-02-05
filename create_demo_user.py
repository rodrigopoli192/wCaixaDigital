from django.contrib.auth import get_user_model

from caixa_nfse.core.models import Tenant

User = get_user_model()

# 1. Get or Create Tenant
tenant, created = Tenant.objects.get_or_create(
    razao_social="Demo Corp",
    defaults={
        "nome_fantasia": "Demo Corp",
        "cnpj": "12.345.678/0001-90",
        "email": "contato@democorp.com",
    },
)
if created:
    print(f"✅ Empresa '{tenant.razao_social}' criada com sucesso.")
else:
    print(f"ℹ️ Empresa '{tenant.razao_social}' já existia.")

# 2. Create Manager User
email = "gerente@democorp.com"
password = "mudar123"

# Check if user exists
if User.objects.filter(email=email).exists():
    user = User.objects.get(email=email)
    print(f"ℹ️ Usuário '{email}' já existe. Atualizando permissões...")
else:
    user = User.objects.create_user(
        email=email, password=password, first_name="Gerente", last_name="Demo", tenant=tenant
    )
    print(f"✅ Usuário '{email}' criado com senha: '{password}'")

# 3. Assign Permissions
user.tenant = tenant
user.pode_aprovar_fechamento = True  # Manager Permission
user.pode_operar_caixa = True
user.pode_emitir_nfse = True
user.save()

print(f"✅ Permissões de GERENTE atribuídas para {user.email}.")
print(f"🔑 Login: {user.email}")
print(f"🔑 Senha: {password}")
