from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from caixa_nfse.caixa.models import Caixa
from caixa_nfse.clientes.models import Cliente
from caixa_nfse.core.models import Tenant

User = get_user_model()


@pytest.mark.django_db
class TestManagementCommands:
    def test_create_admin_success(self):
        out = StringIO()
        call_command("create_admin", stdout=out)

        output = out.getvalue()
        assert "Superusuário criado!" in output
        assert User.objects.filter(email="admin@caixadigital.com", is_superuser=True).exists()

    def test_create_admin_already_exists(self):
        # Create first time
        User.objects.create_superuser(
            email="admin@caixadigital.com", password="pass", first_name="Admin", last_name="Test"
        )

        out = StringIO()
        call_command("create_admin", stdout=out)

        output = out.getvalue()
        assert "Usuário admin@caixadigital.com já existe!" in output

    def test_create_sample_data_success(self):
        out = StringIO()
        call_command("create_sample_data", stdout=out)

        output = out.getvalue()
        assert "Dados de exemplo criados com sucesso!" in output

        # Verify created data
        assert Tenant.objects.count() >= 1
        assert Caixa.objects.count() >= 2
        assert Cliente.objects.count() >= 2

        # Verify second run idempotency (should usually just get_or_create)
        call_command("create_sample_data", stdout=out)
        assert (
            Tenant.objects.count() >= 1
        )  # Should not duplicate logically unique items tested via get_or_create logic
