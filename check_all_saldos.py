"""
Script para verificar o saldo_atual diretamente no banco de dados.
"""

import os
import sys

import django

# Setup Django
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "caixa_nfse.settings")
django.setup()

from caixa_nfse.caixa.models import Caixa

print("=" * 60)
print("📊 VERIFICAÇÃO DE SALDOS - TODOS OS CAIXAS")
print("=" * 60)

caixas = Caixa.objects.all()

for caixa in caixas:
    print(f"\n🏪 {caixa.identificador} (Status: {caixa.get_status_display()})")
    print(f"   💰 Saldo Atual (DB): R$ {caixa.saldo_atual}")

    # Buscar abertura ativa
    abertura_ativa = caixa.aberturas.filter(fechado=False).first()

    if abertura_ativa:
        print("   📝 Abertura Ativa:")
        print(f"      - Saldo Abertura: R$ {abertura_ativa.saldo_abertura}")
        print(f"      - Saldo Movimentos (calc): R$ {abertura_ativa.saldo_movimentos}")
        print(f"      - Editado: {'Sim' if abertura_ativa.saldo_inicial_editado else 'Não'}")

        if abertura_ativa.saldo_inicial_editado:
            print(f"      - Original: R$ {abertura_ativa.saldo_inicial_original}")
            print(f"      - Editado em: {abertura_ativa.saldo_editado_em}")

        # Verificar se está sincronizado
        if caixa.saldo_atual == abertura_ativa.saldo_movimentos:
            print("   ✅ SINCRONIZADO")
        else:
            diff = caixa.saldo_atual - abertura_ativa.saldo_movimentos
            print(f"   ❌ DESSINCRONIZADO - Diferença: R$ {diff}")
    else:
        print("   ℹ️  Sem abertura ativa")

print("\n" + "=" * 60)
