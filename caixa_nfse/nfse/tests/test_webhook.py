"""
Tests for nfse/webhook.py — NFS-e gateway callback endpoint.
"""

import json
import uuid

import pytest
from django.test import RequestFactory, TestCase

from caixa_nfse.nfse.models import (
    EventoFiscal,
    StatusNFSe,
)
from caixa_nfse.nfse.webhook import NFSeWebhookView
from caixa_nfse.tests.factories import (
    ConfiguracaoNFSeFactory,
    NotaFiscalServicoFactory,
    TenantFactory,
)


@pytest.fixture
def tenant(db):
    return TenantFactory()


@pytest.fixture
def config(tenant):
    return ConfiguracaoNFSeFactory(
        tenant=tenant,
        backend="focus_nfe",
        webhook_token="test-webhook-secret-123",
    )


@pytest.fixture
def nota_enviando(config):
    return NotaFiscalServicoFactory(
        tenant=config.tenant,
        status=StatusNFSe.ENVIANDO,
        protocolo="proto-123",
    )


@pytest.fixture
def factory():
    return RequestFactory()


# ── Token Validation ───────────────────────────────────────


class TestWebhookValidation(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.tenant = TenantFactory()
        self.config = ConfiguracaoNFSeFactory(
            tenant=self.tenant,
            backend="focus_nfe",
            webhook_token="valid-token",
        )
        self.view = NFSeWebhookView.as_view()

    def test_no_token_returns_401(self):
        request = self.factory.post(
            "/nfse/webhook/",
            data=json.dumps({"ref": "test"}),
            content_type="application/json",
        )
        response = self.view(request)
        assert response.status_code == 401

    def test_invalid_token_returns_401(self):
        request = self.factory.post(
            "/nfse/webhook/",
            data=json.dumps({"ref": "test"}),
            content_type="application/json",
            HTTP_X_WEBHOOK_TOKEN="wrong-token",
        )
        response = self.view(request)
        assert response.status_code == 401

    def test_valid_token_in_header(self):
        nota = NotaFiscalServicoFactory(
            tenant=self.tenant,
            status=StatusNFSe.ENVIANDO,
        )
        request = self.factory.post(
            "/nfse/webhook/",
            data=json.dumps(
                {
                    "ref": str(nota.pk),
                    "status": "autorizado",
                    "numero": "12345",
                }
            ),
            content_type="application/json",
            HTTP_X_WEBHOOK_TOKEN="valid-token",
        )
        response = self.view(request)
        assert response.status_code == 200

    def test_valid_token_in_query_param(self):
        nota = NotaFiscalServicoFactory(
            tenant=self.tenant,
            status=StatusNFSe.ENVIANDO,
        )
        request = self.factory.post(
            "/nfse/webhook/?token=valid-token",
            data=json.dumps(
                {
                    "ref": str(nota.pk),
                    "status": "autorizado",
                }
            ),
            content_type="application/json",
        )
        response = self.view(request)
        assert response.status_code == 200

    def test_invalid_json_returns_400(self):
        request = self.factory.post(
            "/nfse/webhook/",
            data="not json",
            content_type="application/json",
            HTTP_X_WEBHOOK_TOKEN="valid-token",
        )
        response = self.view(request)
        assert response.status_code == 400

    def test_missing_ref_returns_400(self):
        request = self.factory.post(
            "/nfse/webhook/",
            data=json.dumps({"status": "autorizado"}),
            content_type="application/json",
            HTTP_X_WEBHOOK_TOKEN="valid-token",
        )
        response = self.view(request)
        assert response.status_code == 400


# ── Focus NFe Callbacks ───────────────────────────────────


class TestWebhookFocusNFe(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.tenant = TenantFactory()
        self.config = ConfiguracaoNFSeFactory(
            tenant=self.tenant,
            backend="focus_nfe",
            webhook_token="focus-token",
        )
        self.view = NFSeWebhookView.as_view()

    def test_autorizado_updates_nota(self):
        nota = NotaFiscalServicoFactory(
            tenant=self.tenant,
            status=StatusNFSe.ENVIANDO,
        )
        payload = {
            "ref": str(nota.pk),
            "status": "autorizado",
            "numero": "99001",
            "codigo_verificacao": "ABC123",
            "xml_nfse": "<nfse>ok</nfse>",
            "caminho_xml_nota_fiscal": "https://example.com/danfse.pdf",
            "protocolo": "proto-focus",
        }
        request = self.factory.post(
            "/nfse/webhook/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_WEBHOOK_TOKEN="focus-token",
        )
        response = self.view(request)
        assert response.status_code == 200

        nota.refresh_from_db()
        assert nota.status == StatusNFSe.AUTORIZADA
        assert nota.numero_nfse == 99001
        assert nota.codigo_verificacao == "ABC123"
        assert nota.xml_nfse == "<nfse>ok</nfse>"
        assert nota.pdf_url == "https://example.com/danfse.pdf"

        # EventoFiscal created
        evento = EventoFiscal.objects.filter(nota=nota).last()
        assert evento is not None
        assert "AUTORIZACAO" in evento.tipo

    def test_cancelado_updates_nota(self):
        nota = NotaFiscalServicoFactory(
            tenant=self.tenant,
            status=StatusNFSe.AUTORIZADA,
        )
        payload = {
            "ref": str(nota.pk),
            "status": "cancelado",
            "mensagem": "Cancelada a pedido",
        }
        request = self.factory.post(
            "/nfse/webhook/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_WEBHOOK_TOKEN="focus-token",
        )
        response = self.view(request)
        assert response.status_code == 200

        nota.refresh_from_db()
        assert nota.status == StatusNFSe.CANCELADA

    def test_rejeitado_updates_nota(self):
        nota = NotaFiscalServicoFactory(
            tenant=self.tenant,
            status=StatusNFSe.ENVIANDO,
        )
        payload = {
            "ref": str(nota.pk),
            "status": "erro_autorizacao",
            "mensagem": "Dados inválidos",
        }
        request = self.factory.post(
            "/nfse/webhook/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_WEBHOOK_TOKEN="focus-token",
        )
        response = self.view(request)
        assert response.status_code == 200

        nota.refresh_from_db()
        assert nota.status == StatusNFSe.REJEITADA

    def test_unknown_status_ignored(self):
        nota = NotaFiscalServicoFactory(
            tenant=self.tenant,
            status=StatusNFSe.ENVIANDO,
        )
        payload = {
            "ref": str(nota.pk),
            "status": "processando_autorizacao",
        }
        request = self.factory.post(
            "/nfse/webhook/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_WEBHOOK_TOKEN="focus-token",
        )
        response = self.view(request)
        data = json.loads(response.content)
        assert data["action"] == "ignored"

        nota.refresh_from_db()
        assert nota.status == StatusNFSe.ENVIANDO

    def test_nota_not_found_returns_404(self):
        payload = {"ref": str(uuid.uuid4()), "status": "autorizado"}
        request = self.factory.post(
            "/nfse/webhook/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_WEBHOOK_TOKEN="focus-token",
        )
        response = self.view(request)
        assert response.status_code == 404


# ── TecnoSpeed Callbacks ──────────────────────────────────


class TestWebhookTecnoSpeed(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.tenant = TenantFactory()
        self.config = ConfiguracaoNFSeFactory(
            tenant=self.tenant,
            backend="tecnospeed",
            webhook_token="ts-token",
        )
        self.view = NFSeWebhookView.as_view()

    def test_autorizada_via_situacao(self):
        nota = NotaFiscalServicoFactory(
            tenant=self.tenant,
            status=StatusNFSe.ENVIANDO,
        )
        payload = {
            "id": str(nota.pk),
            "situacao": "autorizada",
            "numero_nfse": "88001",
            "link_pdf": "https://ts.com/pdf/88001",
            "xml": "<nfse>ts-ok</nfse>",
        }
        request = self.factory.post(
            "/nfse/webhook/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_WEBHOOK_TOKEN="ts-token",
        )
        response = self.view(request)
        assert response.status_code == 200

        nota.refresh_from_db()
        assert nota.status == StatusNFSe.AUTORIZADA
        assert nota.pdf_url == "https://ts.com/pdf/88001"

    def test_rejected_via_situacao(self):
        nota = NotaFiscalServicoFactory(
            tenant=self.tenant,
            status=StatusNFSe.ENVIANDO,
        )
        payload = {
            "id": str(nota.pk),
            "situacao": "rejeitada",
            "mensagem": "CNPJ inválido",
        }
        request = self.factory.post(
            "/nfse/webhook/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_WEBHOOK_TOKEN="ts-token",
        )
        response = self.view(request)
        assert response.status_code == 200

        nota.refresh_from_db()
        assert nota.status == StatusNFSe.REJEITADA


# ── Health Check ──────────────────────────────────────────


class TestWebhookHealthCheck(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.view = NFSeWebhookView.as_view()

    def test_get_returns_ok(self):
        request = self.factory.get("/nfse/webhook/")
        response = self.view(request)
        assert response.status_code == 200
        assert response.content == b"OK"
