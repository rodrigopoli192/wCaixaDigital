"""
Script de teste para verificar atualização do saldo_atual após edição do saldo_abertura.
"""

import os
import sys

import django

# Setup Django
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "caixa_nfse.settings")
django.setup()

from caixa_nfse.caixa.models import Caixa

# Buscar um caixa aberto
caixas_abertos = Caixa.objects.filter(status="ABERTO")
if not caixas_abertos.exists():
    print("❌ Nenhum caixa aberto encontrado")
    sys.exit(1)

caixa = caixas_abertos.first()
print(f"📦 Caixa: {caixa.identificador}")
print(f"💰 Saldo Atual (antes): R$ {caixa.saldo_atual}")

# Buscar abertura atual
abertura = caixa.aberturas.filter(fechado=False).first()
if not abertura:
    print("❌ Nenhuma abertura ativa encontrada")
    sys.exit(1)

print("\n📝 Abertura:")
print(f"  - Saldo Abertura: R$ {abertura.saldo_abertura}")
print(f"  - Saldo Movimentos (calculado): R$ {abertura.saldo_movimentos}")
print(f"  - Total Entradas: R$ {abertura.total_entradas}")
print(f"  - Total Saídas: R$ {abertura.total_saidas}")

# Calcular saldo esperado
saldo_esperado = abertura.saldo_abertura + abertura.total_entradas - abertura.total_saidas
print(f"\n🔢 Saldo Esperado: R$ {saldo_esperado}")
print(f"🔢 Saldo Movimentos: R$ {abertura.saldo_movimentos}")
print(f"🔢 Saldo Atual Caixa: R$ {caixa.saldo_atual}")

if saldo_esperado == abertura.saldo_movimentos:
    print("✅ Cálculo de saldo_movimentos está correto")
else:
    print("❌ Cálculo de saldo_movimentos está incorreto")

if caixa.saldo_atual == abertura.saldo_movimentos:
    print("✅ Saldo atual do caixa está sincronizado")
else:
    print("❌ Saldo atual do caixa NÃO está sincronizado")
    print(f"   Diferença: R$ {caixa.saldo_atual - abertura.saldo_movimentos}")
