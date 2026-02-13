"""Verificar Caixa 3 especificamente"""

import os
import sys

import django

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "caixa_nfse.settings")
django.setup()

from caixa_nfse.caixa.models import Caixa

caixa3 = Caixa.objects.filter(identificador__icontains="Caixa 3").first()
if not caixa3:
    print("Caixa 3 não encontrado")
else:
    print(f"Caixa: {caixa3.identificador}")
    print(f"Saldo Atual (DB field): R$ {caixa3.saldo_atual}")

    abertura = caixa3.aberturas.filter(fechado=False).first()
    if abertura:
        print("\nAbertura Atual:")
        print(f"  Saldo Abertura: R$ {abertura.saldo_abertura}")
        print(f"  Entradas: R$ {abertura.total_entradas}")
        print(f"  Saídas: R$ {abertura.total_saidas}")
        print(f"  Saldo Movimentos (calc): R$ {abertura.saldo_movimentos}")
        print(f"  Editado: {abertura.saldo_inicial_editado}")

        saldo_esperado = abertura.saldo_abertura + abertura.total_entradas - abertura.total_saidas
        print(f"\nSaldo Esperado: R$ {saldo_esperado}")
        print(f"Saldo Atual (DB): R$ {caixa3.saldo_atual}")
        print(f"Diferença: R$ {caixa3.saldo_atual - saldo_esperado}")

        # Vamos corrigir agora
        print("\n🔧 CORRIGINDO...")
        caixa3.saldo_atual = abertura.saldo_movimentos
        caixa3.save(update_fields=["saldo_atual"])
        print(f"✅ Saldo atualizado para: R$ {caixa3.saldo_atual}")
