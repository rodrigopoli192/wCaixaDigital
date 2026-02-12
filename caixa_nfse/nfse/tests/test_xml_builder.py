"""
Testes do xml_builder — Construção do XML DPS no padrão nacional.
"""

import pytest

from caixa_nfse.nfse.backends.portal_nacional.xml_builder import (
    NS,
    _gerar_id_dps,
    construir_dps,
    dps_para_string,
)
from caixa_nfse.tests.factories import NotaFiscalServicoFactory, TenantFactory


@pytest.mark.django_db
class TestXmlBuilder:
    def test_constroi_dps_raiz(self):
        """DPS raiz deve ter tag DPS com namespace correto."""
        nota = NotaFiscalServicoFactory()
        dps = construir_dps(nota, nota.tenant)
        assert dps.tag == f"{NS}DPS"

    def test_inf_dps_presente(self):
        """Elemento infDPS deve estar presente com atributo Id."""
        nota = NotaFiscalServicoFactory()
        dps = construir_dps(nota, nota.tenant)
        inf = dps.find(f"{NS}infDPS")
        assert inf is not None
        assert inf.get("Id") is not None
        assert inf.get("Id").startswith("DPS")

    def test_identificacao_presente(self):
        """Grupo de identificação deve conter campos obrigatórios."""
        nota = NotaFiscalServicoFactory()
        dps = construir_dps(nota, nota.tenant)
        inf = dps.find(f"{NS}infDPS")
        ident = inf.find(f"{NS}Id")
        assert ident is not None
        assert ident.find(f"{NS}cLocEmi") is not None
        assert ident.find(f"{NS}dhEmi") is not None
        assert ident.find(f"{NS}serie") is not None
        assert ident.find(f"{NS}nDPS") is not None
        assert ident.find(f"{NS}tpAmb") is not None

    def test_prestador_presente(self):
        """Dados do prestador devem incluir CNPJ e razão social."""
        nota = NotaFiscalServicoFactory()
        dps = construir_dps(nota, nota.tenant)
        inf = dps.find(f"{NS}infDPS")
        prest = inf.find(f"{NS}prest")
        assert prest is not None
        assert prest.find(f"{NS}CNPJ") is not None
        assert prest.find(f"{NS}xNome") is not None

    def test_tomador_com_cpf(self):
        """Tomador PF deve ter tag CPF."""
        nota = NotaFiscalServicoFactory()
        dps = construir_dps(nota, nota.tenant)
        inf = dps.find(f"{NS}infDPS")
        toma = inf.find(f"{NS}toma")
        assert toma is not None
        assert toma.find(f"{NS}xNome") is not None
        # CPF ou CNPJ presente
        cpf = toma.find(f"{NS}CPF")
        cnpj = toma.find(f"{NS}CNPJ")
        assert cpf is not None or cnpj is not None

    def test_servico_presente(self):
        """Grupo de serviço deve incluir código e descrição."""
        nota = NotaFiscalServicoFactory()
        dps = construir_dps(nota, nota.tenant)
        inf = dps.find(f"{NS}infDPS")
        serv = inf.find(f"{NS}serv")
        assert serv is not None
        assert serv.find(f"{NS}cServ") is not None
        assert serv.find(f"{NS}xDescServ") is not None

    def test_valores_presente(self):
        """Grupo de valores deve incluir vServPrest, vBC, vISS e vLiq."""
        nota = NotaFiscalServicoFactory()
        dps = construir_dps(nota, nota.tenant)
        inf = dps.find(f"{NS}infDPS")
        vals = inf.find(f"{NS}valores")
        assert vals is not None
        assert vals.find(f"{NS}vServPrest").text == "100.00"
        assert vals.find(f"{NS}vBC") is not None
        assert vals.find(f"{NS}vISS") is not None
        assert vals.find(f"{NS}vLiq") is not None

    def test_ibs_cbs_ausente_quando_zero(self):
        """Grupo IBSCBS não deve aparecer quando CBS e IBS são zero."""
        nota = NotaFiscalServicoFactory(valor_cbs=0, valor_ibs=0)
        dps = construir_dps(nota, nota.tenant)
        inf = dps.find(f"{NS}infDPS")
        assert inf.find(f"{NS}IBSCBS") is None

    def test_ibs_cbs_presente_quando_preenchido(self):
        """Grupo IBSCBS deve aparecer quando CBS ou IBS > 0."""
        from decimal import Decimal

        nota = NotaFiscalServicoFactory(valor_cbs=Decimal("5.00"), valor_ibs=Decimal("3.00"))
        dps = construir_dps(nota, nota.tenant)
        inf = dps.find(f"{NS}infDPS")
        grupo = inf.find(f"{NS}IBSCBS")
        assert grupo is not None
        assert grupo.find(f"{NS}vCBS").text == "5.00"
        assert grupo.find(f"{NS}vIBS").text == "3.00"

    def test_dps_para_string(self):
        """dps_para_string deve retornar XML válido como string."""
        nota = NotaFiscalServicoFactory()
        dps = construir_dps(nota, nota.tenant)
        xml_str = dps_para_string(dps)
        assert "<?xml version=" in xml_str
        assert "DPS" in xml_str
        assert isinstance(xml_str, str)

    def test_gerar_id_dps_formato(self):
        """ID da DPS deve seguir o formato: DPS + CNPJ(14) + série(5) + número(15)."""
        tenant = TenantFactory(cnpj="12345678000100")
        nota = NotaFiscalServicoFactory(tenant=tenant, numero_rps=42, serie_rps="1")
        id_dps = _gerar_id_dps(nota, tenant)
        assert id_dps.startswith("DPS")
        assert "12345678000100" in id_dps
        # Total: 3 + 14 + 5 + 15 = 37 chars
        assert len(id_dps) == 37

    def test_ambiente_producao(self):
        """tpAmb deve ser '1' para produção."""
        nota = NotaFiscalServicoFactory(ambiente="PRODUCAO")
        dps = construir_dps(nota, nota.tenant)
        inf = dps.find(f"{NS}infDPS")
        ident = inf.find(f"{NS}Id")
        tp_amb = ident.find(f"{NS}tpAmb")
        assert tp_amb.text == "1"

    def test_ambiente_homologacao(self):
        """tpAmb deve ser '2' para homologação."""
        nota = NotaFiscalServicoFactory(ambiente="HOMOLOGACAO")
        dps = construir_dps(nota, nota.tenant)
        inf = dps.find(f"{NS}infDPS")
        ident = inf.find(f"{NS}Id")
        tp_amb = ident.find(f"{NS}tpAmb")
        assert tp_amb.text == "2"

    def test_endereco_prestador(self):
        """Endereço do prestador deve estar presente."""
        nota = NotaFiscalServicoFactory()
        dps = construir_dps(nota, nota.tenant)
        inf = dps.find(f"{NS}infDPS")
        prest = inf.find(f"{NS}prest")
        end = prest.find(f"{NS}end")
        assert end is not None
        assert end.find(f"{NS}xLgr") is not None
        assert end.find(f"{NS}CEP") is not None

    def test_retencoes_federais_opcionais(self):
        """Retenções federais só aparecem quando > 0."""
        nota = NotaFiscalServicoFactory(valor_pis=0, valor_cofins=0)
        dps = construir_dps(nota, nota.tenant)
        inf = dps.find(f"{NS}infDPS")
        vals = inf.find(f"{NS}valores")
        assert vals.find(f"{NS}vPIS") is None
        assert vals.find(f"{NS}vCOFINS") is None

    def test_iss_retido_flag(self):
        """Flag ISS retido deve mapear para tpRetISS = '1'."""
        nota = NotaFiscalServicoFactory(iss_retido=True)
        dps = construir_dps(nota, nota.tenant)
        inf = dps.find(f"{NS}infDPS")
        vals = inf.find(f"{NS}valores")
        assert vals.find(f"{NS}tpRetISS").text == "1"

    def test_tomador_pj_com_cnpj(self):
        """Tomador PJ deve ter tag CNPJ (14 dígitos)."""
        from caixa_nfse.tests.factories import ClienteFactory

        cliente = ClienteFactory(tipo_pessoa="PJ", cpf_cnpj="12345678000199")
        nota = NotaFiscalServicoFactory(cliente=cliente)
        dps = construir_dps(nota, nota.tenant)
        inf = dps.find(f"{NS}infDPS")
        toma = inf.find(f"{NS}toma")
        assert toma.find(f"{NS}CNPJ") is not None
        assert toma.find(f"{NS}CNPJ").text == "12345678000199"

    def test_retencoes_federais_todas_presentes(self):
        """Todas as retenções federais devem aparecer quando preenchidas."""
        from decimal import Decimal

        nota = NotaFiscalServicoFactory(
            valor_pis=Decimal("1.50"),
            valor_cofins=Decimal("2.50"),
            valor_inss=Decimal("3.00"),
            valor_ir=Decimal("4.00"),
            valor_csll=Decimal("1.00"),
        )
        dps = construir_dps(nota, nota.tenant)
        inf = dps.find(f"{NS}infDPS")
        vals = inf.find(f"{NS}valores")

        assert vals.find(f"{NS}vPIS").text == "1.50"
        assert vals.find(f"{NS}vCOFINS").text == "2.50"
        assert vals.find(f"{NS}vINSS").text == "3.00"
        assert vals.find(f"{NS}vIR").text == "4.00"
        assert vals.find(f"{NS}vCSLL").text == "1.00"
