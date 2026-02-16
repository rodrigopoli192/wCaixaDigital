import logging
import os
import traceback as tb

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "caixa_nfse.settings.local")
logging.disable(logging.CRITICAL)
django.setup()

from datetime import date
from decimal import Decimal

from lxml import etree

from caixa_nfse.core.models import Tenant
from caixa_nfse.nfse.backends.portal_nacional.xml_builder import construir_dps, dps_para_string
from caixa_nfse.nfse.backends.portal_nacional.xml_signer import assinar_xml
from caixa_nfse.nfse.models import NotaFiscalServico

t = Tenant.objects.get(pk="eae6ccb6-96e4-48c7-8886-ff995007366b")
ref = NotaFiscalServico.objects.filter(tenant=t).first()


class FN:
    ambiente = "HOMOLOGACAO"
    competencia = date.today()
    local_prestacao_ibge = "5208707"
    serie_rps = 1
    numero_rps = 99993
    cliente = ref.cliente
    servico = ref.servico
    discriminacao = "TESTE ASSINATURA"
    valor_servicos = Decimal("10.00")
    iss_retido = False
    aliquota_iss = Decimal("5.00")


dps = construir_dps(FN(), t)
xml_str = dps_para_string(dps)

with open("_debug_xml_unsigned.xml", "w", encoding="utf-8") as f:
    f.write(xml_str)
print("1. XML sem assinatura salvo")

# Check Id
dps_elem = etree.fromstring(xml_str.encode("utf-8"))
ns = {"nfse": "http://www.sped.fazenda.gov.br/nfse"}
inf = dps_elem.find(".//nfse:infDPS", ns)
print(f"2. infDPS Id: {inf.get('Id') if inf is not None else 'NOT FOUND'}")

# Sign
try:
    cert_bytes = bytes(t.certificado_digital)
    senha = t.certificado_senha or ""
    print(f"3. Cert size: {len(cert_bytes)} bytes, senha: {'*' * len(senha)}")

    xml_assinado = assinar_xml(dps_elem, cert_bytes, senha)
    xml_final = etree.tostring(xml_assinado, xml_declaration=True, encoding="UTF-8").decode("utf-8")

    with open("_debug_xml_signed.xml", "w", encoding="utf-8") as f:
        f.write(xml_final)
    print(f"4. XML assinado salvo ({len(xml_final)} bytes)")

    # Examine signature
    for elem in xml_assinado.iter():
        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        if tag == "Reference":
            print(f"5. Signature Reference URI: {elem.get('URI')}")
        if tag == "CanonicalizationMethod":
            print(f"6. CanonicalizationMethod: {elem.get('Algorithm')}")
        if tag == "SignatureMethod":
            print(f"7. SignatureMethod: {elem.get('Algorithm')}")
        if tag == "DigestMethod":
            print(f"8. DigestMethod: {elem.get('Algorithm')}")
        if tag == "Transform":
            print(f"9. Transform: {elem.get('Algorithm')}")

except Exception as e:
    print(f"ERRO: {e}")
    tb.print_exc()
