import json

import pytest
from django.urls import reverse

from caixa_nfse.clientes.models import Cliente
from caixa_nfse.tests.factories import ClienteFactory, TenantFactory, UserFactory


@pytest.mark.django_db
class TestClienteViews:
    def setup_method(self):
        self.tenant = TenantFactory()
        self.user = UserFactory(tenant=self.tenant)
        self.client_obj = ClienteFactory(tenant=self.tenant, created_by=self.user)

        from django.test import Client

        self.client = Client()
        self.client.force_login(self.user)

    def test_list_access(self):
        url = reverse("clientes:list")
        response = self.client.get(url)
        assert response.status_code == 200
        assert self.client_obj in response.context["object_list"]

    def test_list_tenant_isolation(self):
        other_tenant = TenantFactory()
        other_client = ClienteFactory(tenant=other_tenant)

        url = reverse("clientes:list")
        response = self.client.get(url)
        assert response.status_code == 200
        assert other_client not in response.context["object_list"]

    def test_detail_access(self):
        url = reverse("clientes:detail", kwargs={"pk": self.client_obj.pk})
        response = self.client.get(url)
        assert response.status_code == 200
        assert response.context["object"] == self.client_obj

    def test_detail_tenant_isolation(self):
        other_tenant = TenantFactory()
        other_client = ClienteFactory(tenant=other_tenant)

        url = reverse("clientes:detail", kwargs={"pk": other_client.pk})
        response = self.client.get(url)
        assert response.status_code == 404

    def test_create_get(self):
        url = reverse("clientes:create")
        response = self.client.get(url)
        assert response.status_code == 200
        assert "form" in response.context

    def test_create_htmx_get(self):
        url = reverse("clientes:create")
        response = self.client.get(url, headers={"HX-Request": "true"})
        assert response.status_code == 200
        assert "clientes/partials/modal_form.html" in [t.name for t in response.templates]

    def test_create_post_success(self):
        url = reverse("clientes:create")
        data = {
            "razao_social": "New Client Ltda",
            "cpf_cnpj": "12345678901234",
            "email": "new@client.com",
            # Add other required fields if any in factory defaults
            "tipo_pessoa": "PJ",
            "status": "ATIVO",
        }
        response = self.client.post(url, data)
        assert response.status_code == 302  # Redirect
        assert Cliente.objects.filter(razao_social="New Client Ltda").exists()

    def test_create_post_htmx_success(self):
        url = reverse("clientes:create")
        data = {
            "razao_social": "HTMX Client",
            "cpf_cnpj": "98765432109876",
            "email": "htmx@client.com",
            "tipo_pessoa": "PJ",
        }
        response = self.client.post(url, data, headers={"HX-Request": "true"})
        assert response.status_code == 204  # No Content
        assert "HX-Trigger" in response.headers

        trigger_data = json.loads(response.headers["HX-Trigger"])
        assert "clientCreated" in trigger_data
        assert trigger_data["clientCreated"]["label"] == "HTMX Client"

    def test_list_filters(self):
        url = reverse("clientes:list")

        # Filter matches (using 'q' or whatever param filterview uses, usually 'q' or field names)
        # Check filters.py for exact name. Usually django-filter uses field names.
        # Assuming 'razao_social' or generic 'q' search. Let's try explicit field.
        response = self.client.get(url, {"razao_social": self.client_obj.razao_social})
        assert response.status_code == 200
        assert self.client_obj in response.context["object_list"]

        # Filter no match
        response = self.client.get(url, {"razao_social": "NONEXISTENT"})
        assert response.status_code == 200
        assert len(response.context["object_list"]) == 0

    def test_create_post_htmx_error(self):
        url = reverse("clientes:create")
        data = {
            "razao_social": "",  # Empty required field
            "cpf_cnpj": "invalid",
        }
        response = self.client.post(url, data, headers={"HX-Request": "true"})
        assert response.status_code == 200  # Should return 200 with form errors
        # Assuming your partial template renders errors
        assert "clientes/partials/modal_form.html" in [t.name for t in response.templates]
        assert response.context["form"].errors
        url = reverse("clientes:update", kwargs={"pk": self.client_obj.pk})
        response = self.client.get(url)
        assert response.status_code == 200

    def test_update_post_success(self):
        url = reverse("clientes:update", kwargs={"pk": self.client_obj.pk})
        data = {
            "razao_social": "Updated Name",
            "cpf_cnpj": self.client_obj.cpf_cnpj,  # Keep original
            "email": "updated@test.com",
            "tipo_pessoa": self.client_obj.tipo_pessoa,
        }
        response = self.client.post(url, data)
        assert response.status_code == 302
        self.client_obj.refresh_from_db()
        assert self.client_obj.razao_social == "Updated Name"
        assert self.client_obj.updated_by == self.user

    def test_list_shows_cadastro_incompleto_badge(self):
        self.client_obj.cadastro_completo = False
        self.client_obj.save()

        url = reverse("clientes:list")
        response = self.client.get(url)
        assert response.status_code == 200
        assert "Incompleto" in response.content.decode()

    def test_detail_shows_cadastro_incompleto_badge(self):
        self.client_obj.cadastro_completo = False
        self.client_obj.save()

        url = reverse("clientes:detail", kwargs={"pk": self.client_obj.pk})
        response = self.client.get(url)
        assert response.status_code == 200
        assert "Cadastro Incompleto" in response.content.decode()

    def test_list_filter_cadastro_completo(self):
        incomplete = ClienteFactory(
            tenant=self.tenant,
            created_by=self.user,
            cadastro_completo=False,
        )

        url = reverse("clientes:list")
        response = self.client.get(url, {"cadastro_completo": "false"})
        assert response.status_code == 200
        ids = [c.pk for c in response.context["object_list"]]
        assert incomplete.pk in ids
        assert self.client_obj.pk not in ids
