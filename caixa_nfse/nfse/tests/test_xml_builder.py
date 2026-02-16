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
        """Campos de identificação devem estar em infDPS (filhos diretos)."""
        nota = NotaFiscalServicoFactory()
        dps = construir_dps(nota, nota.tenant)
        inf = dps.find(f"{NS}infDPS")
        # Campos obrigatórios de identificação (filhos diretos de infDPS)
        assert inf.find(f"{NS}cLocEmi") is not None
        assert inf.find(f"{NS}dhEmi") is not None
        assert inf.find(f"{NS}serie") is not None
        assert inf.find(f"{NS}nDPS") is not None
        assert inf.find(f"{NS}tpAmb") is not None

    def test_prestador_presente(self):
        """Dados do prestador devem incluir CNPJ (sem xNome quando tpEmit=1)."""
        nota = NotaFiscalServicoFactory()
        dps = construir_dps(nota, nota.tenant)
        inf = dps.find(f"{NS}infDPS")
        prest = inf.find(f"{NS}prest")
        assert prest is not None
        assert prest.find(f"{NS}CNPJ") is not None
        # E0121: xNome do prestador NÃO deve ser informado quando tpEmit=1
        assert prest.find(f"{NS}xNome") is None
        # E0128: Endereço do prestador NÃO deve ser informado quando tpEmit=1
        assert prest.find(f"{NS}end") is None

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
        """Grupo de serviço deve incluir localização, código tributário e descrição."""
        nota = NotaFiscalServicoFactory()
        dps = construir_dps(nota, nota.tenant)
        inf = dps.find(f"{NS}infDPS")
        serv = inf.find(f"{NS}serv")
        assert serv is not None
        # locPrest é filho de serv
        assert serv.find(f"{NS}locPrest") is not None
        # cServ → cTribNac + xDescServ
        c_serv = serv.find(f"{NS}cServ")
        assert c_serv is not None
        assert c_serv.find(f"{NS}cTribNac") is not None
        assert c_serv.find(f"{NS}xDescServ") is not None

    def test_valores_presente(self):
        """Grupo de valores deve incluir vServPrest e tributos."""
        nota = NotaFiscalServicoFactory()
        dps = construir_dps(nota, nota.tenant)
        inf = dps.find(f"{NS}infDPS")
        vals = inf.find(f"{NS}valores")
        assert vals is not None
        # vServPrest → vServ
        v_serv_prest = vals.find(f"{NS}vServPrest")
        assert v_serv_prest is not None
        assert v_serv_prest.find(f"{NS}vServ") is not None

    def test_ibs_cbs_grupo_nao_implementado(self):
        """Grupo IBSCBS não é gerado pelo xml_builder do Portal Nacional."""
        nota = NotaFiscalServicoFactory(valor_cbs=0, valor_ibs=0)
        dps = construir_dps(nota, nota.tenant)
        inf = dps.find(f"{NS}infDPS")
        assert inf.find(f"{NS}IBSCBS") is None

    def test_dps_para_string(self):
        """dps_para_string deve retornar XML válido como string."""
        nota = NotaFiscalServicoFactory()
        dps = construir_dps(nota, nota.tenant)
        xml_str = dps_para_string(dps)
        assert "<?xml version=" in xml_str
        assert "DPS" in xml_str
        assert isinstance(xml_str, str)

    def test_gerar_id_dps_formato(self):
        """ID da DPS deve seguir o formato: DPS + cMun(7) + tpInsc(1) + CNPJ(14) + série(5) + número(15)."""
        tenant = TenantFactory(cnpj="12345678000100")
        nota = NotaFiscalServicoFactory(tenant=tenant, numero_rps=42, serie_rps="1")
        id_dps = _gerar_id_dps(nota, tenant)
        assert id_dps.startswith("DPS")
        assert "12345678000100" in id_dps
        # Total: 3 + 7 + 1 + 14 + 5 + 15 = 45 chars
        assert len(id_dps) == 45

    def test_ambiente_producao(self):
        """tpAmb deve ser '1' para produção."""
        nota = NotaFiscalServicoFactory(ambiente="PRODUCAO")
        dps = construir_dps(nota, nota.tenant)
        inf = dps.find(f"{NS}infDPS")
        tp_amb = inf.find(f"{NS}tpAmb")
        assert tp_amb.text == "1"

    def test_ambiente_homologacao(self):
        """tpAmb deve ser '2' para homologação."""
        nota = NotaFiscalServicoFactory(ambiente="HOMOLOGACAO")
        dps = construir_dps(nota, nota.tenant)
        inf = dps.find(f"{NS}infDPS")
        tp_amb = inf.find(f"{NS}tpAmb")
        assert tp_amb.text == "2"

    def test_endereco_prestador_ausente_tpemit_1(self):
        """E0128: Endereço do prestador NÃO deve ser informado quando tpEmit=1."""
        nota = NotaFiscalServicoFactory()
        dps = construir_dps(nota, nota.tenant)
        inf = dps.find(f"{NS}infDPS")
        prest = inf.find(f"{NS}prest")
        end = prest.find(f"{NS}end")
        assert end is None

    def test_retencoes_federais_nao_implementadas(self):
        """Retenções federais (vPIS, vCOFINS) não são emitidas no xml_builder do Portal Nacional."""
        nota = NotaFiscalServicoFactory(valor_pis=0, valor_cofins=0)
        dps = construir_dps(nota, nota.tenant)
        inf = dps.find(f"{NS}infDPS")
        vals = inf.find(f"{NS}valores")
        assert vals.find(f"{NS}vPIS") is None
        assert vals.find(f"{NS}vCOFINS") is None

    def test_iss_retido_flag(self):
        """Flag ISS retido deve mapear para tpRetISSQN correspondente."""
        nota = NotaFiscalServicoFactory(iss_retido=True)
        dps = construir_dps(nota, nota.tenant)
        inf = dps.find(f"{NS}infDPS")
        vals = inf.find(f"{NS}valores")
        trib = vals.find(f"{NS}trib")
        trib_mun = trib.find(f"{NS}tribMun")
        tp_ret = trib_mun.find(f"{NS}tpRetISSQN")
        assert tp_ret is not None
        assert tp_ret.text == "2"  # 2=Retido pelo tomador

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

    def test_retencoes_federais_todas_ausentes(self):
        """Retenções federais não são emitidas no portal nacional (hierarquia diferente)."""
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
        # Portal Nacional não usa retenções diretamente em valores
        assert vals.find(f"{NS}vPIS") is None

    def test_tot_trib_simples_nacional(self):
        """Para Simples Nacional (E0712): usar pTotTribSN em vez de indTotTrib."""
        tenant = TenantFactory(regime_tributario="SIMPLES")
        nota = NotaFiscalServicoFactory(tenant=tenant)
        dps = construir_dps(nota, tenant)
        inf = dps.find(f"{NS}infDPS")
        vals = inf.find(f"{NS}valores")
        trib = vals.find(f"{NS}trib")
        tot_trib = trib.find(f"{NS}totTrib")
        assert tot_trib is not None
        assert tot_trib.find(f"{NS}pTotTribSN") is not None
        assert tot_trib.find(f"{NS}indTotTrib") is None
