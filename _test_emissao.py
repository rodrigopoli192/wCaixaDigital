import logging
import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "caixa_nfse.settings.local")
logging.disable(logging.CRITICAL)
django.setup()

from datetime import date
from decimal import Decimal

from caixa_nfse.core.models import Tenant
from caixa_nfse.nfse.models import ConfiguracaoNFSe, EventoFiscal, NotaFiscalServico

t = Tenant.objects.get(pk="eae6ccb6-96e4-48c7-8886-ff995007366b")
config = ConfiguracaoNFSe.objects.get(tenant=t)
ref = NotaFiscalServico.objects.filter(tenant=t).first()

# Usar Goiânia (5208707) em vez de São Paulo (3550308)
MUNICIPIO_GOIANIA = "5208707"

nota = NotaFiscalServico.objects.create(
    tenant=t,
    cliente=ref.cliente,
    servico=ref.servico,
    numero_rps=99991,
    competencia=date.today(),
    discriminacao="TESTE COM MUNICIPIO GOIANIA",
    valor_servicos=Decimal("10.00"),
    base_calculo=Decimal("10.00"),
    aliquota_iss=Decimal("5.00"),
    valor_iss=Decimal("0.50"),
    valor_liquido=Decimal("9.50"),
    local_prestacao_ibge=MUNICIPIO_GOIANIA,
    backend_utilizado=config.backend,
    status="RASCUNHO",
    ambiente=config.ambiente,
)

from caixa_nfse.nfse.tasks import enviar_nfse

try:
    enviar_nfse(str(nota.pk))
except Exception:
    pass

nota.refresh_from_db()
with open("test_emissao_final.txt", "w", encoding="utf-8") as f:
    f.write(f"STATUS: {nota.status}\n")
    f.write(f"BACKEND: {nota.backend_utilizado}\n")
    f.write(f"AMBIENTE: {nota.ambiente or 'N/A'}\n")
    f.write(f"MUNICIPIO: {nota.local_prestacao_ibge}\n")
    f.write(f"ERRO:\n{nota.mensagem_erro or 'nenhum'}\n")
    if nota.numero_nfse:
        f.write(f"NUMERO_NFSE: {nota.numero_nfse}\n")
    if nota.chave_acesso:
        f.write(f"CHAVE: {nota.chave_acesso}\n")
    if nota.protocolo:
        f.write(f"PROTOCOLO: {nota.protocolo}\n")
    f.write("---\n")
    for ev in EventoFiscal.objects.filter(nota=nota).order_by("data_hora"):
        f.write(f"EVENTO: {ev.tipo} | {ev.mensagem or ''}\n")

nota.delete()
print("DONE - see test_emissao_final.txt")
