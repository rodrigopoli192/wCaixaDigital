"""
Tests for Phase 1: ConfiguracaoNFSe model.
"""

import pytest
from django.db import IntegrityError

from caixa_nfse.nfse.models import AmbienteNFSe, BackendNFSe
from caixa_nfse.tests.factories import ConfiguracaoNFSeFactory, TenantFactory


@pytest.mark.django_db
class TestConfiguracaoNFSeModel:
    def test_create_with_defaults(self):
        config = ConfiguracaoNFSeFactory()
        assert config.backend == BackendNFSe.MOCK
        assert config.ambiente == AmbienteNFSe.HOMOLOGACAO
        assert config.gerar_nfse_ao_confirmar is False
        assert config.api_token == ""
        assert config.api_secret == ""

    def test_unique_per_tenant(self):
        tenant = TenantFactory()
        ConfiguracaoNFSeFactory(tenant=tenant)
        with pytest.raises(IntegrityError):
            ConfiguracaoNFSeFactory(tenant=tenant)

    def test_valid_backend_choices(self):
        for choice_value, _ in BackendNFSe.choices:
            config = ConfiguracaoNFSeFactory(backend=choice_value)
            assert config.backend == choice_value

    def test_valid_ambiente_choices(self):
        for choice_value, _ in AmbienteNFSe.choices:
            config = ConfiguracaoNFSeFactory(ambiente=choice_value)
            assert config.ambiente == choice_value

    def test_str_representation(self):
        config = ConfiguracaoNFSeFactory()
        result = str(config)
        assert "Config NFS-e" in result
        assert "Mock" in result

    def test_gerar_nfse_ao_confirmar_toggle(self):
        config = ConfiguracaoNFSeFactory(gerar_nfse_ao_confirmar=True)
        assert config.gerar_nfse_ao_confirmar is True

    def test_api_credentials_stored(self):
        config = ConfiguracaoNFSeFactory(
            backend=BackendNFSe.FOCUS_NFE,
            api_token="tok_abc123",
            api_secret="sec_xyz789",
        )
        assert config.api_token == "tok_abc123"
        assert config.api_secret == "sec_xyz789"

    def test_tenant_access_via_reverse(self):
        config = ConfiguracaoNFSeFactory()
        assert config.tenant.config_nfse == config

    def test_portal_nacional_backend(self):
        config = ConfiguracaoNFSeFactory(backend=BackendNFSe.PORTAL_NACIONAL)
        assert config.get_backend_display() == "Portal Nacional"

    def test_producao_ambiente(self):
        config = ConfiguracaoNFSeFactory(ambiente=AmbienteNFSe.PRODUCAO)
        assert config.get_ambiente_display() == "Produção"
