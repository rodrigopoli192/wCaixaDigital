"""Simple check - qual caixa está dessincronizado?"""

import os
import sys

import django

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "caixa_nfse.settings")
django.setup()

from caixa_nfse.caixa.models import Caixa

for c in Caixa.objects.all():
    print(f"{c.identificador}: DB={c.saldo_atual}", end="")
    ab = c.aberturas.filter(fechado=False).first()
    if ab:
        calc = ab.saldo_movimentos
        print(f" | Calc={calc} | Match={c.saldo_atual == calc}")
    else:
        print(" | sem abertura")
