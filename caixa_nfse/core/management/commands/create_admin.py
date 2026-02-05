"""
Django management command to create a superuser for initial access.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

User = get_user_model()


class Command(BaseCommand):
    help = "Cria um superusuário admin para acesso inicial"

    def handle(self, *args, **options):
        email = "admin@caixadigital.com"
        password = "admin123"

        if User.objects.filter(email=email).exists():
            self.stdout.write(self.style.WARNING(f"Usuário {email} já existe!"))
            return

        User.objects.create_superuser(
            email=email,
            password=password,
            first_name="Admin",
            last_name="Sistema",
        )
        self.stdout.write(self.style.SUCCESS("✅ Superusuário criado!"))
        self.stdout.write(f"   Email: {email}")
        self.stdout.write(f"   Senha: {password}")
        self.stdout.write("")
        self.stdout.write(self.style.WARNING("⚠️  Altere a senha após o primeiro login!"))
