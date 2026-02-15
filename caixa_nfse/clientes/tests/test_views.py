import json
from unittest.mock import MagicMock, patch

import pytest
from django.test import Client
from django.urls import reverse

from caixa_nfse.clientes.models import Cliente
from caixa_nfse.tests.factories import ClienteFactory, TenantFactory, UserFactory


@pytest.mark.django_db
class TestClienteViews:
    def setup_method(self):
        self.tenant = TenantFactory()
        self.user = UserFactory(tenant=self.tenant)
        self.client_obj = ClienteFactory(tenant=self.tenant, created_by=self.user)

        self.client = Client()
        self.client.force_login(self.user)

    # ------------------------------------------------------------------
    # List View
    # ------------------------------------------------------------------

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

    def test_list_filters(self):
        url = reverse("clientes:list")
        response = self.client.get(url, {"razao_social": self.client_obj.razao_social})
        assert response.status_code == 200
        assert self.client_obj in response.context["object_list"]

        response = self.client.get(url, {"razao_social": "NONEXISTENT"})
        assert response.status_code == 200
        assert len(response.context["object_list"]) == 0

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

    def test_list_shows_cadastro_incompleto_badge(self):
        self.client_obj.cadastro_completo = False
        self.client_obj.save()
        url = reverse("clientes:list")
        response = self.client.get(url)
        assert response.status_code == 200
        assert "Incompleto" in response.content.decode()

    def test_list_user_without_tenant_returns_empty(self):
        """TenantMixin branch: user.tenant is None → qs.none()."""
        user_no_tenant = UserFactory(tenant=None)
        client = Client()
        client.force_login(user_no_tenant)
        url = reverse("clientes:list")
        response = client.get(url)
        assert response.status_code == 200
        assert len(response.context["object_list"]) == 0

    # ------------------------------------------------------------------
    # Detail View
    # ------------------------------------------------------------------

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

    def test_detail_shows_cadastro_incompleto_badge(self):
        self.client_obj.cadastro_completo = False
        self.client_obj.save()
        url = reverse("clientes:detail", kwargs={"pk": self.client_obj.pk})
        response = self.client.get(url)
        assert response.status_code == 200
        assert "Cadastro Incompleto" in response.content.decode()

    # ------------------------------------------------------------------
    # Create View
    # ------------------------------------------------------------------

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
            "cpf_cnpj": "12345678000195",
            "email": "new@client.com",
            "tipo_pessoa": "PJ",
            "ativo": True,
        }
        response = self.client.post(url, data)
        assert response.status_code == 302
        assert Cliente.objects.filter(razao_social="New Client Ltda").exists()

    def test_create_post_htmx_success(self):
        url = reverse("clientes:create")
        data = {
            "razao_social": "HTMX Client",
            "cpf_cnpj": "11444777000161",
            "email": "htmx@client.com",
            "tipo_pessoa": "PJ",
            "ativo": True,
        }
        response = self.client.post(url, data, headers={"HX-Request": "true"})
        assert response.status_code == 204
        assert "HX-Trigger" in response.headers

        trigger_data = json.loads(response.headers["HX-Trigger"])
        assert "clientCreated" in trigger_data
        assert trigger_data["clientCreated"]["label"] == "HTMX Client"

    def test_create_post_htmx_error(self):
        url = reverse("clientes:create")
        data = {
            "razao_social": "",
            "cpf_cnpj": "invalid",
        }
        response = self.client.post(url, data, headers={"HX-Request": "true"})
        assert response.status_code == 200
        assert "clientes/partials/modal_form.html" in [t.name for t in response.templates]
        assert response.context["form"].errors

    def test_create_post_error_non_htmx(self):
        """Non-HTMX form error re-renders full template."""
        url = reverse("clientes:create")
        data = {"razao_social": "", "cpf_cnpj": ""}
        response = self.client.post(url, data)
        assert response.status_code == 200
        assert "clientes/cliente_form.html" in [t.name for t in response.templates]
        assert response.context["form"].errors

    # ------------------------------------------------------------------
    # Update View
    # ------------------------------------------------------------------

    def test_update_get(self):
        url = reverse("clientes:update", kwargs={"pk": self.client_obj.pk})
        response = self.client.get(url)
        assert response.status_code == 200
        assert "form" in response.context

    def test_update_post_success(self):
        url = reverse("clientes:update", kwargs={"pk": self.client_obj.pk})
        data = {
            "razao_social": "Updated Name",
            "cpf_cnpj": self.client_obj.cpf_cnpj,
            "email": "updated@test.com",
            "tipo_pessoa": self.client_obj.tipo_pessoa,
        }
        response = self.client.post(url, data)
        assert response.status_code == 302
        self.client_obj.refresh_from_db()
        assert self.client_obj.razao_social == "Updated Name"
        assert self.client_obj.updated_by == self.user

    def test_update_tenant_isolation(self):
        """Cannot update a client from another tenant."""
        other_tenant = TenantFactory()
        other_client = ClienteFactory(tenant=other_tenant)
        url = reverse("clientes:update", kwargs={"pk": other_client.pk})
        response = self.client.get(url)
        assert response.status_code == 404

    def test_update_post_error(self):
        """Form error on update re-renders."""
        url = reverse("clientes:update", kwargs={"pk": self.client_obj.pk})
        data = {
            "razao_social": "",
            "tipo_pessoa": self.client_obj.tipo_pessoa,
        }
        response = self.client.post(url, data)
        assert response.status_code == 200
        assert response.context["form"].errors

    # ------------------------------------------------------------------
    # CEP Lookup View
    # ------------------------------------------------------------------

    def test_cep_lookup_invalid_short(self):
        url = reverse("clientes:cep_lookup")
        response = self.client.get(url, {"cep": "123"})
        assert response.status_code == 400
        assert response.json()["error"] == "CEP inválido"

    def test_cep_lookup_invalid_empty(self):
        url = reverse("clientes:cep_lookup")
        response = self.client.get(url)
        assert response.status_code == 400

    @patch("caixa_nfse.clientes.views.CepLookupView.get")
    def test_cep_lookup_success(self, mock_get):
        """Successful CEP lookup via mocked requests."""
        from django.http import JsonResponse

        mock_get.return_value = JsonResponse(
            {
                "logradouro": "Rua Teste",
                "bairro": "Centro",
                "cidade": "São Paulo",
                "uf": "SP",
                "codigo_ibge": "3550308",
            }
        )
        url = reverse("clientes:cep_lookup")
        response = self.client.get(url, {"cep": "01001000"})
        assert response.status_code == 200

    def test_cep_lookup_success_real_mock(self):
        """Successful CEP lookup with requests.get mocked at module level."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "logradouro": "Praça da Sé",
            "bairro": "Sé",
            "localidade": "São Paulo",
            "uf": "SP",
            "ibge": "3550308",
        }
        mock_response.raise_for_status = MagicMock()

        with patch("requests.get", return_value=mock_response):
            url = reverse("clientes:cep_lookup")
            response = self.client.get(url, {"cep": "01001000"})
            assert response.status_code == 200
            data = response.json()
            assert data["logradouro"] == "Praça da Sé"
            assert data["cidade"] == "São Paulo"
            assert data["codigo_ibge"] == "3550308"

    def test_cep_lookup_not_found(self):
        """CEP exists but ViaCEP returns erro: true."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"erro": True}
        mock_response.raise_for_status = MagicMock()

        with patch("requests.get", return_value=mock_response):
            url = reverse("clientes:cep_lookup")
            response = self.client.get(url, {"cep": "99999999"})
            assert response.status_code == 404
            assert response.json()["error"] == "CEP não encontrado"

    def test_cep_lookup_network_error(self):
        """Network error returns 502."""
        import requests as req_lib

        with patch("requests.get", side_effect=req_lib.RequestException("timeout")):
            url = reverse("clientes:cep_lookup")
            response = self.client.get(url, {"cep": "01001000"})
            assert response.status_code == 502
            assert "Falha" in response.json()["error"]
