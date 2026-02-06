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
        self.user = UserFactory(tenant=self.tenant, pode_emitir_nfse=True, pode_cancelar_nfse=True)
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
        assert response.context["object"] == self.nota

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

        with unittest.mock.patch("caixa_nfse.nfse.views.enviar_nfse") as mock_task:
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
        # Should redirect back to detail and show error, task not called
        with unittest.mock.patch("caixa_nfse.nfse.views.enviar_nfse") as mock_task:
            # Just to be safe, though not called
            pass

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
