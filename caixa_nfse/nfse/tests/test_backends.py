"""
Tests for Phase 1: Backends (MockBackend + Registry).
"""

from unittest.mock import patch

import pytest

from caixa_nfse.nfse.backends.base import (
    BaseNFSeBackend,
    ResultadoCancelamento,
    ResultadoConsulta,
    ResultadoEmissao,
)
from caixa_nfse.nfse.backends.mock import MockBackend
from caixa_nfse.nfse.backends.registry import (
    _BACKEND_MAP,
    get_backend,
    list_backends,
    register_backend,
)
from caixa_nfse.nfse.models import BackendNFSe
from caixa_nfse.tests.factories import (
    ConfiguracaoNFSeFactory,
    NotaFiscalServicoFactory,
    TenantFactory,
)

# ------- MockBackend tests -------


class TestMockBackend:
    def setup_method(self):
        self.backend = MockBackend()

    @pytest.mark.django_db
    def test_emitir_success(self):
        nota = NotaFiscalServicoFactory()
        result = self.backend.emitir(nota, nota.tenant)

        assert isinstance(result, ResultadoEmissao)
        assert result.sucesso is True
        assert result.numero_nfse == str(nota.numero_rps)
        assert result.chave_acesso.startswith("MOCK")
        assert len(result.chave_acesso) == 50
        assert result.codigo_verificacao.startswith("MOCK-")
        assert result.protocolo.startswith("MOCK-")
        assert "mock" in result.xml_retorno
        assert "mock" in result.mensagem.lower()

    @pytest.mark.django_db
    def test_consultar_success(self):
        nota = NotaFiscalServicoFactory()
        result = self.backend.consultar(nota, nota.tenant)

        assert isinstance(result, ResultadoConsulta)
        assert result.sucesso is True
        assert result.status == nota.status
        assert "mock" in result.xml_retorno
        assert "mock" in result.mensagem.lower()

    @pytest.mark.django_db
    def test_cancelar_success(self):
        nota = NotaFiscalServicoFactory()
        result = self.backend.cancelar(nota, nota.tenant, "Motivo teste")

        assert isinstance(result, ResultadoCancelamento)
        assert result.sucesso is True
        assert result.protocolo.startswith("CANCEL-")
        assert "Motivo teste" in result.mensagem

    @pytest.mark.django_db
    def test_baixar_danfse_returns_none(self):
        nota = NotaFiscalServicoFactory()
        result = self.backend.baixar_danfse(nota, nota.tenant)
        assert result is None


# ------- Dataclasses tests -------


class TestResultadoDataclasses:
    def test_resultado_emissao_defaults(self):
        r = ResultadoEmissao(sucesso=True)
        assert r.numero_nfse is None
        assert r.chave_acesso is None
        assert r.mensagem == ""

    def test_resultado_consulta_defaults(self):
        r = ResultadoConsulta(sucesso=False, mensagem="Erro")
        assert r.status is None
        assert r.mensagem == "Erro"

    def test_resultado_cancelamento_defaults(self):
        r = ResultadoCancelamento(sucesso=True)
        assert r.protocolo is None
        assert r.mensagem == ""


# ------- Registry tests -------


@pytest.mark.django_db
class TestRegistry:
    def setup_method(self):
        _BACKEND_MAP.clear()

    def test_get_backend_no_config_returns_mock(self):
        tenant = TenantFactory()
        backend = get_backend(tenant)
        assert isinstance(backend, MockBackend)

    def test_get_backend_with_mock_config(self):
        config = ConfiguracaoNFSeFactory(backend=BackendNFSe.MOCK)
        backend = get_backend(config.tenant)
        assert isinstance(backend, MockBackend)

    def test_get_backend_unknown_backend_falls_back(self):
        config = ConfiguracaoNFSeFactory(backend="nonexistent")
        backend = get_backend(config.tenant)
        assert isinstance(backend, MockBackend)

    def test_register_custom_backend(self):
        class DummyBackend(BaseNFSeBackend):
            def emitir(self, nota, tenant):
                return ResultadoEmissao(sucesso=True, mensagem="dummy")

            def consultar(self, nota, tenant):
                return ResultadoConsulta(sucesso=True)

            def cancelar(self, nota, tenant, motivo):
                return ResultadoCancelamento(sucesso=True)

            def baixar_danfse(self, nota, tenant):
                return None

        register_backend("dummy", DummyBackend)
        config = ConfiguracaoNFSeFactory(backend="dummy")
        backend = get_backend(config.tenant)
        assert isinstance(backend, DummyBackend)

    def test_list_backends_includes_mock(self):
        backends = list_backends()
        assert "mock" in backends
        assert backends["mock"] is MockBackend

    def test_list_backends_returns_copy(self):
        backends = list_backends()
        backends["fake"] = None
        assert "fake" not in list_backends()

    def test_get_backend_config_access_error(self):
        """If accessing config_nfse fails, fallback to mock."""
        tenant = TenantFactory()
        with patch(
            "caixa_nfse.nfse.backends.registry._get_config",
            return_value=None,
        ):
            backend = get_backend(tenant)
            assert isinstance(backend, MockBackend)
