"""
Testes do xml_signer — Assinatura digital XMLDSIG com certificado A1.
"""

from unittest.mock import MagicMock, patch

import pytest
from lxml import etree

from caixa_nfse.nfse.backends.portal_nacional.xml_signer import (
    _carregar_certificado,
    _detectar_reference_uri,
    assinar_xml,
)


class TestDetectarReferenceUri:
    def test_detecta_id_no_elemento(self):
        """Deve encontrar atributo Id e retornar com '#' prefixado."""
        xml = etree.fromstring('<root><child Id="ABC123"/></root>')
        uri = _detectar_reference_uri(xml)
        assert uri == "#ABC123"

    def test_retorna_vazio_sem_id(self):
        """Se nenhum elemento tiver Id, retorna string vazia."""
        xml = etree.fromstring("<root><child/></root>")
        uri = _detectar_reference_uri(xml)
        assert uri == ""

    def test_detecta_primeiro_id(self):
        """Deve retornar o primeiro Id encontrado na árvore."""
        xml = etree.fromstring('<root><a Id="FIRST"/><b Id="SECOND"/></root>')
        uri = _detectar_reference_uri(xml)
        assert uri == "#FIRST"


class TestCarregarCertificado:
    def test_certificado_invalido_levanta_erro(self):
        """Bytes inválidos devem levantar ValueError."""
        with pytest.raises(ValueError, match="Erro ao carregar certificado"):
            _carregar_certificado(b"bytes_invalidos", "senha123")

    @patch("caixa_nfse.nfse.backends.portal_nacional.xml_signer.pkcs12.load_key_and_certificates")
    def test_certificado_sem_chave_levanta_erro(self, mock_load):
        """Certificado sem chave privada deve levantar ValueError."""
        mock_load.return_value = (None, MagicMock(), [])
        with pytest.raises(ValueError, match="chave privada ou certificado ausente"):
            _carregar_certificado(b"cert_data", "senha")

    @patch("caixa_nfse.nfse.backends.portal_nacional.xml_signer.pkcs12.load_key_and_certificates")
    def test_certificado_sem_cert_levanta_erro(self, mock_load):
        """Certificado sem certificado público deve levantar ValueError."""
        mock_load.return_value = (MagicMock(), None, [])
        with pytest.raises(ValueError, match="chave privada ou certificado ausente"):
            _carregar_certificado(b"cert_data", "senha")

    @patch("caixa_nfse.nfse.backends.portal_nacional.xml_signer.pkcs12.load_key_and_certificates")
    def test_certificado_valido_retorna_tupla(self, mock_load):
        """Certificado válido retorna (chave, cert, cadeia)."""
        mock_key = MagicMock()
        mock_cert = MagicMock()
        mock_chain = [MagicMock()]
        mock_load.return_value = (mock_key, mock_cert, mock_chain)
        chave, cert, cadeia = _carregar_certificado(b"cert_data", "senha")
        assert chave is mock_key
        assert cert is mock_cert
        assert cadeia == mock_chain

    @patch("caixa_nfse.nfse.backends.portal_nacional.xml_signer.pkcs12.load_key_and_certificates")
    def test_cadeia_none_retorna_lista_vazia(self, mock_load):
        """Se cadeia for None, deve retornar lista vazia."""
        mock_load.return_value = (MagicMock(), MagicMock(), None)
        _, _, cadeia = _carregar_certificado(b"cert_data", "senha")
        assert cadeia == []


class TestAssinarXml:
    @patch("caixa_nfse.nfse.backends.portal_nacional.xml_signer._carregar_certificado")
    @patch("caixa_nfse.nfse.backends.portal_nacional.xml_signer.XMLSigner")
    def test_assina_com_reference_uri_automatico(self, mock_signer_cls, mock_carregar):
        """Deve detectar reference_uri automaticamente pelo Id."""
        mock_key = MagicMock()
        mock_cert = MagicMock()
        mock_carregar.return_value = (mock_key, mock_cert, [])

        mock_signer = MagicMock()
        mock_signer.sign.return_value = etree.fromstring("<signed/>")
        mock_signer_cls.return_value = mock_signer

        xml = etree.fromstring('<DPS><infDPS Id="DPS123"/></DPS>')
        resultado = assinar_xml(xml, b"cert", "senha")

        assert resultado is not None
        mock_signer.sign.assert_called_once()

    @patch("caixa_nfse.nfse.backends.portal_nacional.xml_signer._carregar_certificado")
    @patch("caixa_nfse.nfse.backends.portal_nacional.xml_signer.XMLSigner")
    def test_assina_com_reference_uri_explicitoo(self, mock_signer_cls, mock_carregar):
        """Deve usar reference_uri explícito quando fornecido."""
        mock_carregar.return_value = (MagicMock(), MagicMock(), [])
        mock_signer = MagicMock()
        mock_signer.sign.return_value = etree.fromstring("<signed/>")
        mock_signer_cls.return_value = mock_signer

        xml = etree.fromstring("<DPS/>")
        assinar_xml(xml, b"cert", "senha", reference_uri="#CUSTOM")

        call_kwargs = mock_signer.sign.call_args
        assert call_kwargs[1]["reference_uri"] == "#CUSTOM"
