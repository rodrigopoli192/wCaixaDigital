import unittest
from datetime import timedelta

import pytest
from django.utils import timezone

from caixa_nfse.nfse import tasks
from caixa_nfse.nfse.models import EventoFiscal, StatusNFSe, TipoEventoFiscal
from caixa_nfse.tests.factories import NotaFiscalServicoFactory, TenantFactory


@pytest.mark.django_db
class TestNFSeTasks:
    def setup_method(self):
        self.tenant = TenantFactory()
        self.nota = NotaFiscalServicoFactory(tenant=self.tenant, status=StatusNFSe.RASCUNHO)

    def test_enviar_nfse_success(self):
        # Test successful execution
        result = tasks.enviar_nfse(str(self.nota.pk))

        self.nota.refresh_from_db()
        assert result["success"] is True
        assert self.nota.status == StatusNFSe.AUTORIZADA
        assert self.nota.numero_nfse == self.nota.numero_rps
        assert EventoFiscal.objects.filter(nota=self.nota, tipo=TipoEventoFiscal.ENVIO).exists()
        assert EventoFiscal.objects.filter(
            nota=self.nota, tipo=TipoEventoFiscal.AUTORIZACAO
        ).exists()

    def test_enviar_nfse_not_found(self):
        # Test with invalid ID
        import uuid

        result = tasks.enviar_nfse(str(uuid.uuid4()))
        assert result["success"] is False
        assert result["error"] == "Nota não encontrada"

    def test_enviar_nfse_retry_on_exception(self):
        # Mocking retry to avoid actual waiting
        with unittest.mock.patch("caixa_nfse.nfse.tasks.enviar_nfse.retry") as mock_retry:
            # We need to mock something inside to raise exception
            # Easiest is to mock NotaFiscalServico.objects.get to raise generic Exception
            with unittest.mock.patch(
                "caixa_nfse.nfse.models.NotaFiscalServico.objects.get"
            ) as mock_get:
                mock_get.side_effect = Exception("Connection Error")

                tasks.enviar_nfse(str(self.nota.pk))

                mock_retry.assert_called()

    def test_verificar_certificados_vencendo(self):
        # Create tenants with expiring certificates
        today = timezone.now().date()

        t1 = TenantFactory(certificado_validade=today + timedelta(days=30))
        t2 = TenantFactory(certificado_validade=today + timedelta(days=15))
        t3 = TenantFactory(certificado_validade=today + timedelta(days=7))
        t4 = TenantFactory(certificado_validade=today + timedelta(days=100))  # Should not be listed

        result = tasks.verificar_certificados_vencendo()
        alertas = result["alertas"]

        assert len(alertas) >= 3
        tenants_alerted = [a["tenant"] for a in alertas]
        assert t1.razao_social in tenants_alerted
        assert t2.razao_social in tenants_alerted
        assert t3.razao_social in tenants_alerted
        assert t4.razao_social not in tenants_alerted

    def test_consultar_lote_nfse(self):
        nota2 = NotaFiscalServicoFactory(tenant=self.tenant)
        import uuid

        invalid_id = str(uuid.uuid4())

        ids = [str(self.nota.pk), str(nota2.pk), invalid_id]

        result = tasks.consultar_lote_nfse(ids)
        res_list = result["resultados"]

        assert len(res_list) == 3
        # Verify valid ones
        found_nota = next(r for r in res_list if r["id"] == str(self.nota.pk))
        assert found_nota["status"] == self.nota.status

        # Verify invalid one
        found_invalid = next(r for r in res_list if r["id"] == invalid_id)
        assert "error" in found_invalid
