import unittest

import pytest
from django.urls import reverse

from caixa_nfse.nfse.models import NotaFiscalServico, StatusNFSe
from caixa_nfse.tests.factories import (
    ClienteFactory,
    NotaFiscalServicoFactory,
    ServicoMunicipalFactory,
    TenantFactory,
    UserFactory,
)


@pytest.mark.django_db
class TestNFSeViews:
    def setup_method(self):
        self.tenant = TenantFactory()
        self.user = UserFactory(
            tenant=self.tenant,
            pode_emitir_nfse=True,
            pode_cancelar_nfse=True,
            pode_aprovar_fechamento=True,
        )
        self.servico = ServicoMunicipalFactory()
        self.cliente = ClienteFactory(tenant=self.tenant)
        self.nota = NotaFiscalServicoFactory(
            tenant=self.tenant,
            status=StatusNFSe.RASCUNHO,
            servico=self.servico,
            cliente=self.cliente,
        )

        from django.test import Client

        self.client = Client()
        self.client.force_login(self.user)

    def test_list_access(self):
        url = reverse("nfse:list")
        response = self.client.get(url)
        assert response.status_code == 200
        assert self.nota in response.context["notas"]

    def test_detail_access(self):
        url = reverse("nfse:detail", kwargs={"pk": self.nota.pk})
        response = self.client.get(url)
        assert response.status_code == 200
        assert response.context["nota"] == self.nota

    def test_create_success(self):
        url = reverse("nfse:create")
        data = {
            "cliente": self.cliente.pk,
            "servico": self.servico.pk,
            "discriminacao": "Test Service",
            "competencia": "2023-01-01",
            "valor_servicos": "100.00",
            "valor_deducoes": "0",
            "valor_pis": "0",
            "valor_cofins": "0",
            "valor_inss": "0",
            "valor_ir": "0",
            "valor_csll": "0",
            "aliquota_iss": "5.00",
            "iss_retido": False,
            "local_prestacao_ibge": "3550308",
        }
        response = self.client.post(url, data)
        assert response.status_code == 302
        assert NotaFiscalServico.objects.filter(discriminacao="Test Service").exists()

    def test_update_restricted_status(self):
        # Can update RASCUNHO
        url = reverse("nfse:update", kwargs={"pk": self.nota.pk})
        response = self.client.get(url)
        assert response.status_code == 200

        # Cannot update ENVIANDO
        self.nota.status = StatusNFSe.ENVIANDO
        self.nota.save()
        response = self.client.get(url)
        assert response.status_code == 404  # filtered out by get_queryset

    def test_enviar_trigger_task(self):
        url = reverse("nfse:enviar", kwargs={"pk": self.nota.pk})

        with unittest.mock.patch("caixa_nfse.nfse.tasks.enviar_nfse") as mock_task:
            response = self.client.post(url)
            assert response.status_code == 302
            mock_task.delay.assert_called_once_with(str(self.nota.pk))

            self.nota.refresh_from_db()
            assert self.nota.status == StatusNFSe.ENVIANDO

    def test_enviar_fail_not_rascunho(self):
        self.nota.status = StatusNFSe.AUTORIZADA
        self.nota.save()
        url = reverse("nfse:enviar", kwargs={"pk": self.nota.pk})

        response = self.client.post(url)
        assert response.status_code == 302

        self.nota.refresh_from_db()
        assert self.nota.status == StatusNFSe.AUTORIZADA

    def test_cancelar_success(self):
        self.nota.status = StatusNFSe.AUTORIZADA
        self.nota.save()
        url = reverse("nfse:cancelar", kwargs={"pk": self.nota.pk})

        # Currently the view says "Development", so we just expect redirect and message
        response = self.client.post(url, {"motivo": "Erro de digitação"})
        assert response.status_code == 302

    def test_cancelar_fail_motivo_missing(self):
        self.nota.status = StatusNFSe.AUTORIZADA
        self.nota.save()
        url = reverse("nfse:cancelar", kwargs={"pk": self.nota.pk})

        response = self.client.post(url, {})  # No motivo
        assert response.status_code == 302
        # Message assertion would be ideal

    def test_download_xml(self):
        self.nota.xml_rps = "<xml>RPS</xml>"
        self.nota.save()
        url = reverse("nfse:xml", kwargs={"pk": self.nota.pk})

        response = self.client.get(url)
        assert response.status_code == 200
        assert response["Content-Type"] == "application/xml"
        assert b"<xml>RPS</xml>" in response.content

    def test_download_xml_missing(self):
        self.nota.xml_rps = ""
        self.nota.xml_nfse = ""
        self.nota.save()
        url = reverse("nfse:xml", kwargs={"pk": self.nota.pk})

        response = self.client.get(url)
        assert response.status_code == 302  # Redirect failure

    # --- NFSeListView filtering tests ----

    def test_list_filter_by_status(self):
        url = reverse("nfse:list")
        response = self.client.get(url, {"status": StatusNFSe.RASCUNHO})
        assert response.status_code == 200
        assert self.nota in response.context["notas"]
        assert "stats" in response.context
        assert response.context["stats"]["total"] >= 1

    def test_list_filter_by_cliente(self):
        url = reverse("nfse:list")
        response = self.client.get(url, {"cliente": self.cliente.razao_social[:5]})
        assert response.status_code == 200
        assert self.nota in response.context["notas"]

    def test_list_filter_no_results(self):
        url = reverse("nfse:list")
        response = self.client.get(url, {"status": StatusNFSe.CANCELADA})
        assert response.status_code == 200
        assert len(response.context["notas"]) == 0

    # --- NFSeDetailView events test ---

    def test_detail_has_eventos_context(self):
        url = reverse("nfse:detail", kwargs={"pk": self.nota.pk})
        response = self.client.get(url)
        assert response.status_code == 200
        assert "eventos" in response.context

    # --- Operador isolation test ---

    def test_operador_sees_only_own_notes(self):
        operador = UserFactory(
            tenant=self.tenant, pode_emitir_nfse=True, pode_aprovar_fechamento=False
        )
        self.nota.created_by = self.user  # belongs to gerente
        self.nota.save()

        from django.test import Client

        client2 = Client()
        client2.force_login(operador)

        url = reverse("nfse:list")
        response = client2.get(url)
        assert response.status_code == 200
        assert self.nota not in response.context["notas"]
        assert response.context["is_gerente"] is False


@pytest.mark.django_db
class TestNFSeConfigView:
    def setup_method(self):
        self.tenant = TenantFactory()
        self.user = UserFactory(
            tenant=self.tenant, pode_emitir_nfse=True, pode_aprovar_fechamento=True
        )

        from django.test import Client

        self.client = Client()
        self.client.force_login(self.user)

    def test_config_get_creates_default(self):
        from caixa_nfse.nfse.models import ConfiguracaoNFSe

        url = reverse("nfse:config")
        response = self.client.get(url)
        assert response.status_code == 200
        assert ConfiguracaoNFSe.objects.filter(tenant=self.tenant).exists()

    def test_config_post_save(self):
        from caixa_nfse.nfse.models import ConfiguracaoNFSe

        url = reverse("nfse:config")
        data = {
            "backend": "mock",
            "ambiente": "HOMOLOGACAO",
            "gerar_nfse_ao_confirmar": "on",
            "api_token": "test-token",
            "api_secret": "test-secret",
        }
        response = self.client.post(url, data)
        assert response.status_code == 302
        config = ConfiguracaoNFSe.objects.get(tenant=self.tenant)
        assert config.api_token == "test-token"
        assert config.gerar_nfse_ao_confirmar is True

    def test_config_access_denied_no_permission(self):
        user2 = UserFactory(
            tenant=self.tenant, pode_emitir_nfse=True, pode_aprovar_fechamento=False
        )
        self.client.force_login(user2)
        url = reverse("nfse:config")
        response = self.client.get(url)
        assert response.status_code == 403


@pytest.mark.django_db
class TestNFSeTestarConexaoView:
    def setup_method(self):
        self.tenant = TenantFactory()
        self.user = UserFactory(
            tenant=self.tenant, pode_emitir_nfse=True, pode_aprovar_fechamento=True
        )

        from django.test import Client

        self.client = Client()
        self.client.force_login(self.user)

    def test_testar_ohne_config(self):
        url = reverse("nfse:testar")
        response = self.client.post(url)
        assert response.status_code == 200
        assert (
            "Sem Configuração" in response.content.decode()
            or "Configure" in response.content.decode()
        )

    def test_testar_with_config(self):
        from caixa_nfse.nfse.models import ConfiguracaoNFSe

        ConfiguracaoNFSe.objects.create(tenant=self.tenant, backend="mock")
        url = reverse("nfse:testar")
        with unittest.mock.patch("caixa_nfse.nfse.backends.get_backend") as mock_get:
            mock_backend = unittest.mock.MagicMock()
            del mock_backend.testar_conexao  # No testar_conexao method
            mock_get.return_value = mock_backend
            response = self.client.post(url)
            assert response.status_code == 200
            assert (
                "Backend Carregado" in response.content.decode()
                or "configurado" in response.content.decode()
            )

    def test_testar_with_error(self):
        from caixa_nfse.nfse.models import ConfiguracaoNFSe

        ConfiguracaoNFSe.objects.create(tenant=self.tenant, backend="mock")
        url = reverse("nfse:testar")
        with unittest.mock.patch("caixa_nfse.nfse.backends.get_backend") as mock_get:
            mock_get.side_effect = Exception("Connection refused")
            response = self.client.post(url)
            assert response.status_code == 200
            assert "Erro" in response.content.decode()


@pytest.mark.django_db
class TestNFSeDANFSeView:
    def setup_method(self):
        self.tenant = TenantFactory()
        self.user = UserFactory(tenant=self.tenant, pode_emitir_nfse=True)
        self.servico = ServicoMunicipalFactory()
        self.cliente = ClienteFactory(tenant=self.tenant)
        self.nota = NotaFiscalServicoFactory(
            tenant=self.tenant,
            servico=self.servico,
            cliente=self.cliente,
        )

        from django.test import Client

        self.client = Client()
        self.client.force_login(self.user)

    def test_danfse_redirect_with_pdf(self):
        self.nota.pdf_url = "https://example.com/danfse.pdf"
        self.nota.save()
        url = reverse("nfse:danfse", kwargs={"pk": self.nota.pk})
        response = self.client.get(url)
        assert response.status_code == 302
        assert "example.com" in response["Location"]

    def test_danfse_missing_redirect(self):
        self.nota.pdf_url = ""
        self.nota.save()
        url = reverse("nfse:danfse", kwargs={"pk": self.nota.pk})
        response = self.client.get(url)
        assert response.status_code == 302
        assert "danfse" not in response["Location"]
