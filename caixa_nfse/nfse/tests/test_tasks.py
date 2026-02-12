"""
Tests for nfse/tasks.py — enviar_nfse, emitir_nfse_movimento,
verificar_certificados_vencendo, consultar_lote_nfse.
"""

import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone

from caixa_nfse.nfse import tasks
from caixa_nfse.nfse.models import EventoFiscal, StatusNFSe, TipoEventoFiscal
from caixa_nfse.tests.factories import (
    ClienteFactory,
    MovimentoCaixaFactory,
    NotaFiscalServicoFactory,
    ServicoMunicipalFactory,
    TenantFactory,
)


@pytest.mark.django_db
class TestEnviarNfse:
    def setup_method(self):
        self.tenant = TenantFactory()
        self.nota = NotaFiscalServicoFactory(
            tenant=self.tenant,
            status=StatusNFSe.RASCUNHO,
        )

    @patch("caixa_nfse.nfse.tasks.get_backend")
    def test_sucesso_emissao(self, mock_get_backend):
        mock_backend = MagicMock()
        mock_backend.emitir.return_value = MagicMock(
            sucesso=True,
            numero_nfse=12345,
            codigo_verificacao="ABC123",
            chave_acesso="CHAVE50DIGITOS",
            protocolo="PROT001",
            xml_retorno="<xml>ok</xml>",
            pdf_url="https://pdf.example.com/danfse.pdf",
            mensagem="NFS-e emitida com sucesso",
        )
        mock_get_backend.return_value = mock_backend

        result = tasks.enviar_nfse(str(self.nota.pk))

        assert result["success"] is True
        self.nota.refresh_from_db()
        assert self.nota.status == StatusNFSe.AUTORIZADA
        assert self.nota.numero_nfse == 12345
        assert self.nota.codigo_verificacao == "ABC123"
        assert self.nota.chave_acesso == "CHAVE50DIGITOS"
        assert self.nota.protocolo == "PROT001"

        # Check events
        assert EventoFiscal.objects.filter(nota=self.nota, tipo=TipoEventoFiscal.ENVIO).exists()
        assert EventoFiscal.objects.filter(
            nota=self.nota, tipo=TipoEventoFiscal.AUTORIZACAO
        ).exists()

    @patch("caixa_nfse.nfse.tasks.get_backend")
    def test_rejeicao_emissao(self, mock_get_backend):
        mock_backend = MagicMock()
        mock_backend.emitir.return_value = MagicMock(
            sucesso=False,
            mensagem="CNPJ inválido",
            xml_retorno="<erro>CNPJ</erro>",
        )
        mock_get_backend.return_value = mock_backend

        result = tasks.enviar_nfse(str(self.nota.pk))

        assert result["success"] is False
        assert result["error"] == "CNPJ inválido"
        self.nota.refresh_from_db()
        assert self.nota.status == StatusNFSe.REJEITADA

        assert EventoFiscal.objects.filter(nota=self.nota, tipo=TipoEventoFiscal.REJEICAO).exists()

    def test_nota_nao_encontrada(self):
        result = tasks.enviar_nfse(str(uuid.uuid4()))
        assert result["success"] is False
        assert result["error"] == "Nota não encontrada"

    @patch("caixa_nfse.nfse.tasks.get_backend")
    def test_retry_on_exception(self, mock_get_backend):
        mock_get_backend.side_effect = Exception("Connection Error")

        with patch("caixa_nfse.nfse.tasks.enviar_nfse.retry") as mock_retry:
            tasks.enviar_nfse(str(self.nota.pk))
            mock_retry.assert_called()

    @patch("caixa_nfse.nfse.tasks.get_backend")
    def test_sucesso_resultado_campos_none(self, mock_get_backend):
        """Test fallback when result fields are None."""
        mock_backend = MagicMock()
        mock_backend.emitir.return_value = MagicMock(
            sucesso=True,
            numero_nfse=None,
            codigo_verificacao=None,
            chave_acesso=None,
            protocolo=None,
            xml_retorno=None,
            pdf_url=None,
            mensagem=None,
        )
        mock_get_backend.return_value = mock_backend

        result = tasks.enviar_nfse(str(self.nota.pk))

        assert result["success"] is True
        self.nota.refresh_from_db()
        assert self.nota.numero_nfse == self.nota.numero_rps  # fallback
        assert self.nota.codigo_verificacao == ""

    @patch("caixa_nfse.nfse.tasks.get_backend")
    def test_rejeicao_mensagem_none(self, mock_get_backend):
        """Test fallback when rejection message is None."""
        mock_backend = MagicMock()
        mock_backend.emitir.return_value = MagicMock(
            sucesso=False,
            mensagem=None,
            xml_retorno=None,
        )
        mock_get_backend.return_value = mock_backend

        result = tasks.enviar_nfse(str(self.nota.pk))

        assert result["success"] is False
        assert result["error"] == "Emissão rejeitada"


@pytest.mark.django_db
class TestEmitirNfseMovimento:
    def setup_method(self):
        self.tenant = TenantFactory()
        self.cliente = ClienteFactory(tenant=self.tenant)
        self.servico = ServicoMunicipalFactory()
        self.movimento = MovimentoCaixaFactory(
            abertura__caixa__tenant=self.tenant,
            cliente=self.cliente,
            valor=Decimal("150.00"),
        )

    @patch("caixa_nfse.nfse.tasks.enviar_nfse")
    @patch("caixa_nfse.nfse.tasks.criar_nfse_de_movimento")
    def test_cria_nota_e_chama_enviar(self, mock_criar, mock_enviar):
        nota = NotaFiscalServicoFactory(tenant=self.tenant)
        mock_criar.return_value = nota
        mock_enviar.return_value = {"success": True, "nota_id": str(nota.pk)}

        result = tasks.emitir_nfse_movimento(str(self.movimento.pk))

        mock_criar.assert_called_once_with(self.movimento)
        mock_enviar.assert_called_once_with(str(nota.pk))
        assert result["success"] is True

    @patch("caixa_nfse.nfse.tasks.enviar_nfse")
    def test_pula_criacao_se_nota_existe(self, mock_enviar):
        nota = NotaFiscalServicoFactory(tenant=self.tenant)
        self.movimento.nota_fiscal = nota
        self.movimento.save(update_fields=["nota_fiscal"])
        mock_enviar.return_value = {"success": True}

        result = tasks.emitir_nfse_movimento(str(self.movimento.pk))

        mock_enviar.assert_called_once_with(str(nota.pk))
        assert result["success"] is True

    def test_movimento_nao_encontrado(self):
        result = tasks.emitir_nfse_movimento(str(uuid.uuid4()))
        assert result["success"] is False
        assert result["error"] == "Movimento não encontrado"

    @patch("caixa_nfse.nfse.tasks.criar_nfse_de_movimento")
    def test_erro_value_error(self, mock_criar):
        mock_criar.side_effect = ValueError("sem cliente vinculado")

        result = tasks.emitir_nfse_movimento(str(self.movimento.pk))

        assert result["success"] is False
        assert "sem cliente vinculado" in result["error"]

    @patch("caixa_nfse.nfse.tasks.criar_nfse_de_movimento")
    def test_retry_on_generic_exception(self, mock_criar):
        mock_criar.side_effect = Exception("DB Error")

        with patch("caixa_nfse.nfse.tasks.emitir_nfse_movimento.retry") as mock_retry:
            tasks.emitir_nfse_movimento(str(self.movimento.pk))
            mock_retry.assert_called()


@pytest.mark.django_db
class TestVerificarCertificados:
    def test_alerta_30_15_7_dias(self):
        today = timezone.now().date()

        t1 = TenantFactory(certificado_validade=today + timedelta(days=30))
        t2 = TenantFactory(certificado_validade=today + timedelta(days=15))
        t3 = TenantFactory(certificado_validade=today + timedelta(days=7))
        TenantFactory(certificado_validade=today + timedelta(days=100))

        result = tasks.verificar_certificados_vencendo()
        alertas = result["alertas"]

        assert len(alertas) >= 3
        tenants_alerted = [a["tenant"] for a in alertas]
        assert t1.razao_social in tenants_alerted
        assert t2.razao_social in tenants_alerted
        assert t3.razao_social in tenants_alerted


@pytest.mark.django_db
class TestConsultarLoteNfse:
    def test_consulta_com_validos_e_invalidos(self):
        tenant = TenantFactory()
        nota = NotaFiscalServicoFactory(tenant=tenant)
        invalid_id = str(uuid.uuid4())

        ids = [str(nota.pk), invalid_id]
        result = tasks.consultar_lote_nfse(ids)
        res_list = result["resultados"]

        assert len(res_list) == 2
        found_nota = next(r for r in res_list if r["id"] == str(nota.pk))
        assert found_nota["status"] == nota.status

        found_invalid = next(r for r in res_list if r["id"] == invalid_id)
        assert "error" in found_invalid
